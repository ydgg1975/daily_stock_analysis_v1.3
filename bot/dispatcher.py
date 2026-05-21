# -*- coding: utf-8 -*-
"""
===================================
Command dispatcher
===================================

Parses commands, matches handlers, and dispatches execution.
"""

import asyncio
import logging
import re
import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Type, Callable

from bot.models import BotMessage, BotResponse
from bot.commands.base import BotCommand

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter

    Limits each user request rate with a sliding window.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: Maximum requests inside the window.
            window_seconds: Window duration in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        """
        Check whether the user may send a request.

        Args:
            user_id: User identifier.

        Returns:
            Whether it is allowed.
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean expired records.
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if t > window_start
        ]

        # Check whether the limit is exceeded.
        if len(self._requests[user_id]) >= self.max_requests:
            return False

        # Record this request.
        self._requests[user_id].append(now)
        return True

    def get_remaining(self, user_id: str) -> int:
        """Get remaining allowed request count."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean expired records.
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if t > window_start
        ]

        return max(0, self.max_requests - len(self._requests[user_id]))


class CommandDispatcher:
    """
    Command dispatcher

    Responsibilities:
    1. Register and manage command handlers.
    2. Parse commands and arguments from messages.
    3. Dispatch commands to the matching handler.
    4. Handle unknown commands and errors.

    Example:
        dispatcher = CommandDispatcher()
        dispatcher.register(AnalyzeCommand())
        dispatcher.register(HelpCommand())

        response = dispatcher.dispatch(message)
    """

    def __init__(
        self,
        command_prefix: str = "/",
        rate_limit_requests: int = 10,
        rate_limit_window: int = 60,
        admin_users: Optional[List[str]] = None
    ):
        """
        Args:
            command_prefix: Command prefix, default "/".
            rate_limit_requests: Rate limit: maximum requests inside the window.
            rate_limit_window: Rate limit: window duration in seconds.
            admin_users: Administrator user ID list.
        """
        self.command_prefix = command_prefix
        self.admin_users = set(admin_users or [])

        self._commands: Dict[str, BotCommand] = {}
        self._aliases: Dict[str, str] = {}
        self._rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)

        # Callback used by the help command to list commands.
        self._help_command_getter: Optional[Callable] = None

    def register(self, command: BotCommand) -> None:
        """
        Register command

        Args:
            command: Command instance.
        """
        name = command.name.lower()

        if name in self._commands:
            logger.warning(f"[Dispatcher] Command '{name}' already exists and will be overwritten")

        self._commands[name] = command
        logger.debug(f"[Dispatcher] Register command: {name}")

        # Register alias
        for alias in command.aliases:
            alias_lower = alias.lower()
            if alias_lower in self._aliases:
                logger.warning(f"[Dispatcher] Alias '{alias_lower}' already exists and will be overwritten")
            self._aliases[alias_lower] = name
            logger.debug(f"[Dispatcher] Register alias: {alias_lower} -> {name}")

    def register_class(self, command_class: Type[BotCommand]) -> None:
        """
        Register command class automatically.

        Args:
            command_class: Command class.
        """
        self.register(command_class())

    def unregister(self, name: str) -> bool:
        """
        Unregister command

        Args:
            name: Command name.

        Returns:
            Whether unregister succeeded.
        """
        name = name.lower()

        if name not in self._commands:
            return False

        command = self._commands.pop(name)

        # Remove aliases.
        for alias in command.aliases:
            self._aliases.pop(alias.lower(), None)

        logger.debug(f"[Dispatcher] Unregister command: {name}")
        return True

    def get_command(self, name: str) -> Optional[BotCommand]:
        """
        Get command

        Supports lookup by command name or alias.

        Args:
            name: Command name or alias.

        Returns:
            Command instance, or None.
        """
        name = name.lower()

        # Check command name first.
        if name in self._commands:
            return self._commands[name]

        # Then check aliases.
        if name in self._aliases:
            return self._commands.get(self._aliases[name])

        return None

    def list_commands(self, include_hidden: bool = False) -> List[BotCommand]:
        """
        List all commands

        Args:
            include_hidden: Whether to include hidden commands.

        Returns:
            Command list.
        """
        commands = list(self._commands.values())

        if not include_hidden:
            commands = [c for c in commands if not c.hidden]

        return sorted(commands, key=lambda c: c.name)

    def is_admin(self, user_id: str) -> bool:
        """Check whether the user is an administrator."""
        return user_id in self.admin_users

    def add_admin(self, user_id: str) -> None:
        """Add administrator."""
        self.admin_users.add(user_id)

    def remove_admin(self, user_id: str) -> None:
        """Remove administrator."""
        self.admin_users.discard(user_id)

    def dispatch(self, message: BotMessage) -> BotResponse:
        """Dispatch a message synchronously.

        Preserves compatibility for synchronous callers; actual logic is delegated to `dispatch_async()`.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self._dispatch_sync(message)

        result_holder: Dict[str, BotResponse] = {}
        error_holder: Dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_holder["response"] = self._dispatch_sync(message)
            except BaseException as exc:  # pragma: no cover
                error_holder["error"] = exc

        worker = threading.Thread(target=_runner, daemon=True)
        worker.start()
        worker.join()

        if "error" in error_holder:
            raise error_holder["error"]

        return result_holder.get("response", BotResponse.error_response("명령 실행에 실패했습니다."))

    def _prepare_dispatch(self, message: BotMessage) -> tuple[Optional[str], List[str], Optional[BotCommand], Optional[BotResponse]]:
        """Run shared dispatch pre-checks for sync/async entrypoints."""
        if not self._rate_limiter.is_allowed(message.user_id):
            remaining_time = self._rate_limiter.window_seconds
            return None, [], None, BotResponse.error_response(
                f"요청이 너무 잦습니다. {remaining_time}초 후 다시 시도하세요."
            )

        cmd_name, args = message.get_command_and_args(self.command_prefix)
        if cmd_name is None:
            return None, args, None, None

        logger.info(f"[Dispatcher] Command received: {cmd_name}, args: {args}, user: {message.user_name}")

        command = self.get_command(cmd_name)
        if command is None:
            return cmd_name, args, None, BotResponse.error_response(
                f"알 수 없는 명령: {cmd_name}\n"
                f"`{self.command_prefix}help`를 보내 사용 가능한 명령을 확인하세요."
            )

        if command.admin_only and not self.is_admin(message.user_id):
            return cmd_name, args, None, BotResponse.error_response("이 명령은 관리자 권한이 필요합니다.")

        error_msg = command.validate_args(args)
        if error_msg:
            return cmd_name, args, None, BotResponse.error_response(
                f"{error_msg}\n사용법: `{command.usage}`"
            )

        return cmd_name, args, command, None

    def _dispatch_sync(self, message: BotMessage) -> BotResponse:
        """Pure synchronous dispatch path for webhook/stream integrations."""
        cmd_name, args, command, early_response = self._prepare_dispatch(message)
        if early_response is not None:
            return early_response

        if cmd_name is None:
            nl_result = self._try_nl_routing_sync(message)
            if nl_result is not None:
                return nl_result
            if message.mentioned:
                return BotResponse.text_response(
                    "안녕하세요. 주식 분석 도우미입니다.\n"
                    f"`{self.command_prefix}help`를 보내 사용 가능한 명령을 확인하세요."
                )
            return BotResponse.text_response("")

        if command is None:
            return BotResponse.error_response("명령 실행에 실패했습니다.")

        try:
            response = command.execute(message, args)
            logger.info(f"[Dispatcher] Command {cmd_name} executed successfully")
            return response
        except Exception as e:
            logger.error(f"[Dispatcher] Command {cmd_name} failed: {e}")
            logger.exception(e)
            return BotResponse.error_response(f"명령 실행에 실패했습니다: {str(e)[:100]}")

    async def dispatch_async(self, message: BotMessage) -> BotResponse:
        """
        Dispatch a message asynchronously to the matching command.

        Args:
            message: Message object.

        Returns:
            Response object.
        """
        cmd_name, args, command, early_response = self._prepare_dispatch(message)
        if early_response is not None:
            return early_response

        if cmd_name is None:
            # Not a command — try natural language routing before falling back
            nl_result = await self._try_nl_routing(message)
            if nl_result is not None:
                return nl_result
            # No NL match — check if @mentioned for a help hint
            if message.mentioned:
                return BotResponse.text_response(
                    "안녕하세요. 주식 분석 도우미입니다.\n"
                    f"`{self.command_prefix}help`를 보내 사용 가능한 명령을 확인하세요."
                )
            # Ignore non-command messages.
            return BotResponse.text_response("")

        if command is None:
            return BotResponse.error_response("명령 실행에 실패했습니다.")

        # 6. Execute command.
        try:
            response = await command.execute_async(message, args)
            logger.info(f"[Dispatcher] Command {cmd_name} executed successfully")
            return response
        except Exception as e:
            logger.error(f"[Dispatcher] Command {cmd_name} failed: {e}")
            logger.exception(e)
            return BotResponse.error_response(f"명령 실행에 실패했습니다: {str(e)[:100]}")

    def set_help_command_getter(self, getter: Callable) -> None:
        """
        Set the command list getter for the help command.

        Used by HelpCommand to get the command list.

        Args:
            getter: Callback function returning the command list.
        """
        self._help_command_getter = getter

    # ------------------------------------------------------------------ #
    #  Natural language routing (LLM-based)                              #
    # ------------------------------------------------------------------ #

    # Lightweight intent-parsing prompt.  Asks the LLM to output a small
    # JSON object so we can route to the right command.
    _NL_PARSE_PROMPT = """\
You are a stock analysis assistant router. Given a user message, determine whether it contains a stock-analysis request.

Return a JSON object and nothing else with these fields:
- "intent": one of "analysis", "chat", "none"
  * "analysis": the user wants stock analysis, diagnosis, or comparison
  * "chat": the user is asking a general finance-related question
  * "none": the message is irrelevant or you are unsure
- "codes": a list of stock codes mentioned, or an empty list.
  Format: A-share 6-digit ("600519"), HK with prefix ("hk00700"), US ticker uppercase ("AAPL").
- "strategy": strategy or technique name if specified, else null. Examples: "MACD", "trend", "chan_theory".

Examples:
User: "analyze 600519 and 000858"
{"intent":"analysis","codes":["600519","000858"],"strategy":null}

User: "check AAPL with MACD"
{"intent":"analysis","codes":["AAPL"],"strategy":"MACD"}

User: "how is the market today?"
{"intent":"chat","codes":[],"strategy":null}

User: "what is the weather tomorrow?"
{"intent":"none","codes":[],"strategy":null}

User: "600519"
{"intent":"analysis","codes":["600519"],"strategy":null}
"""

    # Cheap pre-filter: only invoke LLM when the message plausibly contains
    # stock-related content.  This regex checks for:
    #   - 6-digit A-share / BSE codes (0/3/6 and 43/83/87/88/92 prefixes)
    #   - HK codes like hk00700
    #   - 2-5 uppercase ASCII letters (US tickers)
    #   - Common finance/analysis keywords (Korean and English)
    _NL_PREFILTER = re.compile(
        r'(?:[036]\d{5}|(?:43|83|87|88|92)\d{4})'  # A-share / BSE 6-digit codes
        r'|(?:hk|HK)\d{5}'                    # HK code
        r'|(?<![a-zA-Z])[A-Z]{2,5}(?![a-zA-Z])'  # US ticker, uppercase only
        r'|\ubd84\uc11d|\uc870\ud68c|\ubd10\uc918|\uc0b4\ud3b4|\uac80\ud1a0|\uc9c4\ub2e8|\uc5b4\ub54c|\ud750\ub984|\ucd94\uc138|\uc804\ub7b5'
        r'|\ub9e4\uc218|\ub9e4\ub3c4|\ubcf4\uc720|\uad00\ub9dd|\ubaa9\ud45c\uac00|\uc190\uc808|\uc9c0\uc9c0|\uc800\ud56d|\uae30\uc220\uc801|\uae30\ubcf8\uc801|\ub9ac\uc2a4\ud06c'
        r'|(?i:analyz|stock|buy|sell|trend|backtest|strateg)',
    )

    _NL_NAME_CLEANUP_PATTERNS = (
        r'[?!\'"()\[\]{}<>]+',
        r'(?i:\b(?:please|analy[sz]e|analysis|research|check|look\s+at|stock|ticker|trend|price)\b)',
        r'(?:\ubd84\uc11d|\uc870\ud68c|\ubd10\uc918|\uc0b4\ud3b4|\uac80\ud1a0|\uc9c4\ub2e8|\ud3c9\uac00|\uc54c\ub824\uc918)\s*',
        r'(?:\ucd5c\uadfc|\ud604\uc7ac|\uc624\ub298|\uc774\uc885\ubaa9|\uc8fc\uc2dd|\uc885\ubaa9)\s*',
        r'(?:\ud750\ub984|\uc0c1\ud669|\uc131\uacfc|\uc5b4\ub54c|\uac00\ub2a5\ud560\uae4c|\uc0b4\uae4c|\ud314\uae4c|\uae30\uc220\uc801|\uae30\ubcf8\uc801|\uc804\ub7b5)\s*',
        r'\s+',
    )

    @classmethod
    def _passes_nl_prefilter(cls, text: str) -> bool:
        """Return whether the message is worth the LLM intent-routing cost."""
        if cls._NL_PREFILTER.search(text):
            return True

        stripped = (text or "").strip()
        if " " in stripped or len(stripped) > 10:
            return False

        from src.agent.orchestrator import _extract_stock_code

        return bool(_extract_stock_code(stripped))

    async def _try_nl_routing(self, message: BotMessage) -> Optional[BotResponse]:
        """Route a non-command message to the appropriate command via LLM intent parsing.

        Two-layer approach to balance cost and accuracy:
        1. **Cheap regex pre-filter**: skip messages that clearly have no stock
           or finance content (avoids LLM cost for irrelevant messages).
        2. **LLM intent parsing**: extract intent, stock codes, and strategy
           from the user text with full multilingual support.

        Only activates when:
        - ``AGENT_NL_ROUTING=true`` in config, **and**
        - the message is in a private chat, **or** the bot was @mentioned.

        Returns ``BotResponse`` if a route was found, ``None`` otherwise.
        """
        from src.config import get_config
        config = get_config()

        if not getattr(config, 'agent_nl_routing', False):
            return None

        # Only handle private chat or @mentioned messages to avoid hijacking
        is_private = message.chat_type.value == "private"
        if not is_private and not message.mentioned:
            return None

        # Keep Bot-side Agent entrypoints behind explicit opt-in so NL routing
        # cannot bypass AGENT_MODE=false.
        if not getattr(config, 'agent_mode', False):
            return None

        text = message.content.strip()
        if not text or len(text) > 500:
            return None

        # Layer 1: cheap pre-filter — skip obviously irrelevant messages
        if not self._passes_nl_prefilter(text):
            return None

        # Layer 2: LLM intent parsing — extract codes, intent, strategy
        parsed = await self._parse_intent_via_llm(text, config)
        if parsed is None:
            return None

        intent = parsed.get("intent", "none")
        codes = parsed.get("codes") or []
        strategy = parsed.get("strategy")

        if intent == "none":
            return None

        if intent == "analysis" and not codes:
            resolved_code = self._resolve_stock_code_from_text(text)
            if resolved_code:
                codes = [resolved_code]

        # "chat" intent → route to /chat with original text
        if intent == "chat":
            chat_cmd = self.get_command("chat")
            if chat_cmd:
                logger.info("[Dispatcher] NL routing → /chat: %s", text[:60])
                return await chat_cmd.execute_async(message, [text])
            return None

        # "analysis" intent → route to /ask
        if intent == "analysis" and codes:
            ask_cmd = self.get_command("ask")
            if not ask_cmd:
                return None

            # Build args: "code1,code2 [strategy]"
            code_str = ",".join(codes[:5])  # cap at 5
            args = [code_str]
            if strategy:
                args.append(strategy)

            logger.info(
                "[Dispatcher] NL routing → /ask %s (strategy=%s, text=%s)",
                code_str, strategy, text[:60],
            )
            return await ask_cmd.execute_async(message, args)

        return None

    def _try_nl_routing_sync(self, message: BotMessage) -> Optional[BotResponse]:
        """Synchronous companion to `_try_nl_routing` for legacy call sites."""
        from src.config import get_config

        config = get_config()
        if not getattr(config, 'agent_nl_routing', False):
            return None

        is_private = message.chat_type.value == "private"
        if not is_private and not message.mentioned:
            return None

        if not getattr(config, 'agent_mode', False):
            return None

        text = message.content.strip()
        if not text or len(text) > 500:
            return None

        if not self._passes_nl_prefilter(text):
            return None

        parsed = self._parse_intent_via_llm_sync(text, config)
        if parsed is None:
            return None

        intent = parsed.get("intent", "none")
        codes = parsed.get("codes") or []
        strategy = parsed.get("strategy")

        if intent == "none":
            return None

        if intent == "analysis" and not codes:
            resolved_code = self._resolve_stock_code_from_text(text)
            if resolved_code:
                codes = [resolved_code]

        if intent == "chat":
            chat_cmd = self.get_command("chat")
            if chat_cmd:
                logger.info("[Dispatcher] NL routing → /chat: %s", text[:60])
                return chat_cmd.execute(message, [text])
            return None

        if intent == "analysis" and codes:
            ask_cmd = self.get_command("ask")
            if not ask_cmd:
                return None

            code_str = ",".join(codes[:5])
            args = [code_str]
            if strategy:
                args.append(strategy)

            logger.info(
                "[Dispatcher] NL routing → /ask %s (strategy=%s, text=%s)",
                code_str, strategy, text[:60],
            )
            return ask_cmd.execute(message, args)

        return None

    @staticmethod
    async def _parse_intent_via_llm(text: str, config) -> Optional[dict]:
        """Call LLM to parse user intent.  Returns parsed dict or None on failure."""
        try:
            from src.agent.llm_adapter import LLMToolAdapter

            messages = [
                {"role": "system", "content": CommandDispatcher._NL_PARSE_PROMPT},
                {"role": "user", "content": text},
            ]
            adapter = LLMToolAdapter(config)
            resp = await asyncio.to_thread(
                adapter.call_text,
                messages,
                temperature=0,
                max_tokens=200,
                timeout=10,
            )
            return CommandDispatcher._parse_intent_payload(resp.content or "")
        except Exception as exc:
            logger.debug("[Dispatcher] NL parse LLM call failed: %s", exc)
            return None

    @staticmethod
    def _parse_intent_via_llm_sync(text: str, config) -> Optional[dict]:
        """Synchronous variant for webhook/stream integrations."""
        try:
            from src.agent.llm_adapter import LLMToolAdapter

            messages = [
                {"role": "system", "content": CommandDispatcher._NL_PARSE_PROMPT},
                {"role": "user", "content": text},
            ]
            adapter = LLMToolAdapter(config)
            resp = adapter.call_text(
                messages,
                temperature=0,
                max_tokens=200,
                timeout=10,
            )
            return CommandDispatcher._parse_intent_payload(resp.content or "")
        except Exception as exc:
            logger.debug("[Dispatcher] NL parse LLM call failed: %s", exc)
            return None

    @staticmethod
    def _parse_intent_payload(raw: str) -> Optional[dict]:
        """Parse the JSON payload returned by the intent-routing LLM call."""
        import json as _json

        cleaned = (raw or "").strip()
        if not cleaned:
            return None

        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            result = _json.loads(cleaned)
        except _json.JSONDecodeError:
            logger.debug("[Dispatcher] NL parse: invalid JSON from LLM: %s", cleaned[:200])
            return None

        if isinstance(result, dict) and "intent" in result:
            return result

        logger.debug("[Dispatcher] NL parse: unexpected structure: %s", cleaned[:200])
        return None

    @classmethod
    def _resolve_stock_code_from_text(cls, text: str) -> Optional[str]:
        """Best-effort stock name/code resolution for NL-routed analysis requests."""
        from data_provider.base import canonical_stock_code
        from src.data.stock_mapping import STOCK_NAME_MAP
        from src.services.name_to_code_resolver import resolve_name_to_code

        def _iter_candidates(raw_text: str) -> List[str]:
            candidates: List[str] = []
            stripped = (raw_text or "").strip()
            if stripped:
                candidates.append(stripped)

            cleaned = stripped
            for pattern in cls._NL_NAME_CLEANUP_PATTERNS:
                cleaned = re.sub(pattern, " ", cleaned)
            cleaned = cleaned.strip().strip()
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

            for source in list(candidates):
                for token in re.findall(r'[A-Za-z][A-Za-z0-9\.]{0,9}|[\u4e00-\u9fff]{2,12}', source):
                    normalized = token.strip().strip()
                    if normalized and normalized not in candidates:
                        candidates.append(normalized)

            return sorted(candidates, key=len, reverse=True)

        def _unique_partial_match(candidate: str) -> Optional[str]:
            if not re.search(r'[\u4e00-\u9fff]', candidate):
                return None
            matches = [
                code for code, stock_name in STOCK_NAME_MAP.items()
                if candidate and candidate in stock_name
            ]
            unique_matches = list(dict.fromkeys(matches))
            if len(unique_matches) == 1:
                return canonical_stock_code(unique_matches[0])
            return None

        candidates = _iter_candidates(text)

        # Prefer deterministic local alias/partial-name matches before any
        # resolver path that may touch online market data providers.
        for candidate in candidates:
            partial = _unique_partial_match(candidate)
            if partial:
                return partial

        for candidate in candidates:
            resolved = resolve_name_to_code(candidate)
            if resolved:
                return canonical_stock_code(resolved)

        return None


# Global dispatcher instance.
_dispatcher: Optional[CommandDispatcher] = None


def get_dispatcher() -> CommandDispatcher:
    """
    Get the global dispatcher instance.

    Uses a singleton; initializes and registers commands on first call.
    """
    global _dispatcher

    if _dispatcher is None:
        from src.config import get_config

        config = get_config()

        # Create dispatcher.
        _dispatcher = CommandDispatcher(
            command_prefix=getattr(config, 'bot_command_prefix', '/'),
            rate_limit_requests=getattr(config, 'bot_rate_limit_requests', 10),
            rate_limit_window=getattr(config, 'bot_rate_limit_window', 60),
            admin_users=getattr(config, 'bot_admin_users', []),
        )

        # Auto-register all commands.
        from bot.commands import ALL_COMMANDS
        for command_class in ALL_COMMANDS:
            _dispatcher.register_class(command_class)

        logger.info(f"[Dispatcher] Initialization complete; registered {len(_dispatcher._commands)} commands")

    return _dispatcher


def reset_dispatcher() -> None:
    """Reset the global dispatcher, mainly for tests."""
    global _dispatcher
    _dispatcher = None
