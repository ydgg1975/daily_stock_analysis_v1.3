# -*- coding: utf-8 -*-

"""

===================================

minglingfenfaqi

===================================



fuzejieximingling?걈ipeichuliqi?갽enfazhixing??
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

    jiandandepinlvxianzhiqi



    jiyuhuadongchuangkousuanfa竊똸ianzhimeigeyonghudeqingqiupinlv??
    """



    def __init__(self, max_requests: int = 10, window_seconds: int = 60):

        """

        Args:

            max_requests: chuangkouneizuidaqingqiushu

            window_seconds: chuangkoushijian竊늤iao竊?
        """

        self.max_requests = max_requests

        self.window_seconds = window_seconds

        self._requests: Dict[str, List[float]] = defaultdict(list)



    def is_allowed(self, user_id: str) -> bool:

        """

        jianchayonghushifouyunxuqingqiu



        Args:

            user_id: yonghubiaoshi



        Returns:

            shifouyunxu

        """

        now = time.time()

        window_start = now - self.window_seconds



        # qingliguoqirecord

        self._requests[user_id] = [

            t for t in self._requests[user_id]

            if t > window_start

        ]



        # jianchashifouchaoxian

        if len(self._requests[user_id]) >= self.max_requests:

            return False



        # recordbenciqingqiu

        self._requests[user_id].append(now)

        return True



    def get_remaining(self, user_id: str) -> int:

        """huoqushengyukeyongqingqiushu"""

        now = time.time()

        window_start = now - self.window_seconds



        # qingliguoqirecord

        self._requests[user_id] = [

            t for t in self._requests[user_id]

            if t > window_start

        ]



        return max(0, self.max_requests - len(self._requests[user_id]))





class CommandDispatcher:

    """

    minglingfenfaqi



    zhize竊?
    1. zhuceheguanliminglingchuliqi

    2. jiexixiaoxizhongdeminglinghecanshu

    3. fenfaminglingdaoduiyingchuliqi

    4. chuliweizhiminglinghecuowu



    shiyongshili竊?
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

            command_prefix: minglingqianzhui竊똫oren "/"

            rate_limit_requests: pinlvxianzhi竊쉉huangkouneizuidaqingqiushu

            rate_limit_window: pinlvxianzhi竊쉉huangkoushijian竊늤iao竊?
            admin_users: guanliyuanyonghu ID liebiao

        """

        self.command_prefix = command_prefix

        self.admin_users = set(admin_users or [])



        self._commands: Dict[str, BotCommand] = {}

        self._aliases: Dict[str, str] = {}

        self._rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)



        # huidiaohanshu竊쉎uoqubangzhuminglingdeminglingliebiao

        self._help_command_getter: Optional[Callable] = None



    def register(self, command: BotCommand) -> None:

        """

        zhucemingling



        Args:

            command: minglingshili

        """

        name = command.name.lower()



        if name in self._commands:

            logger.warning(f"[Dispatcher] mingling '{name}' yicunzai竊똨iangbeifugai")



        self._commands[name] = command

        logger.debug(f"[Dispatcher] zhucemingling: {name}")



        # zhucebieming

        for alias in command.aliases:

            alias_lower = alias.lower()

            if alias_lower in self._aliases:

                logger.warning(f"[Dispatcher] bieming '{alias_lower}' yicunzai竊똨iangbeifugai")

            self._aliases[alias_lower] = name

            logger.debug(f"[Dispatcher] zhucebieming: {alias_lower} -> {name}")



    def register_class(self, command_class: Type[BotCommand]) -> None:

        """

        zhuceminglinglei竊늷idongshilihua竊?


        Args:

            command_class: minglinglei

        """

        self.register(command_class())



    def unregister(self, name: str) -> bool:

        """

        zhuxiaomingling



        Args:

            name: minglingmingcheng



        Returns:

            shifouchenggongzhuxiao

        """

        name = name.lower()



        if name not in self._commands:

            return False



        command = self._commands.pop(name)



        # yichubieming

        for alias in command.aliases:

            self._aliases.pop(alias.lower(), None)



        logger.debug(f"[Dispatcher] zhuxiaomingling: {name}")

        return True



    def get_command(self, name: str) -> Optional[BotCommand]:

        """

        huoqumingling



        zhichiminglingminghebiemingchaxun??


        Args:

            name: minglingminghuobieming



        Returns:

            minglingshili竊똦uo None

        """

        name = name.lower()



        # xianchaminglingming

        if name in self._commands:

            return self._commands[name]



        # zaichabieming

        if name in self._aliases:

            return self._commands.get(self._aliases[name])



        return None



    def list_commands(self, include_hidden: bool = False) -> List[BotCommand]:

        """

        liechusuoyoumingling



        Args:

            include_hidden: shifoubaohanyincangmingling



        Returns:

            minglingliebiao

        """

        commands = list(self._commands.values())



        if not include_hidden:

            commands = [c for c in commands if not c.hidden]



        return sorted(commands, key=lambda c: c.name)



    def is_admin(self, user_id: str) -> bool:

        """jianchayonghushifoushiguanliyuan"""

        return user_id in self.admin_users



    def add_admin(self, user_id: str) -> None:

        """addguanliyuan"""

        self.admin_users.add(user_id)



    def remove_admin(self, user_id: str) -> None:

        """yichuguanliyuan"""

        self.admin_users.discard(user_id)



    def dispatch(self, message: BotMessage) -> BotResponse:

        """Dispatch a message synchronously."""

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



        return result_holder.get("response", BotResponse.error_response("minglingzhixingshibai"))



    def _prepare_dispatch(self, message: BotMessage) -> tuple[Optional[str], List[str], Optional[BotCommand], Optional[BotResponse]]:

        """Run shared dispatch pre-checks for sync/async entrypoints."""

        if not self._rate_limiter.is_allowed(message.user_id):

            remaining_time = self._rate_limiter.window_seconds

            return None, [], None, BotResponse.error_response(

                f"qingqiuguoyupinfan竊똰ing {remaining_time} miaohouzaishi"

            )



        cmd_name, args = message.get_command_and_args(self.command_prefix)

        if cmd_name is None:

            return None, args, None, None



        logger.info(f"[Dispatcher] shoudaomingling: {cmd_name}, canshu: {args}, yonghu: {message.user_name}")



        command = self.get_command(cmd_name)

        if command is None:

            return cmd_name, args, None, BotResponse.error_response(

                f"Unknown command: {cmd_name}\n"
                f"Send `{self.command_prefix}help` to view available commands."

            )



        if command.admin_only and not self.is_admin(message.user_id):

            return cmd_name, args, None, BotResponse.error_response("ciminglingxuyaoguanliyuanquanxian")



        error_msg = command.validate_args(args)

        if error_msg:

            return cmd_name, args, None, BotResponse.error_response(

                f"{error_msg}\nyongfa: `{command.usage}`"

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

                    f"Send `{self.command_prefix}help` to view available commands."

                )

            return BotResponse.text_response("")



        if command is None:

            return BotResponse.error_response("minglingzhixingshibai")



        try:

            response = command.execute(message, args)

            logger.info(f"[Dispatcher] mingling {cmd_name} zhixingchenggong")

            return response

        except Exception as e:

            logger.error(f"[Dispatcher] mingling {cmd_name} zhixingshibai: {e}")

            logger.exception(e)

            return BotResponse.error_response(f"minglingzhixingshibai: {str(e)[:100]}")



    async def dispatch_async(self, message: BotMessage) -> BotResponse:

        """

        yibufenfaxiaoxidaoduiyingmingling



        Args:

            message: xiaoxiduixiang



        Returns:

            xiangyingduixiang

        """

        cmd_name, args, command, early_response = self._prepare_dispatch(message)

        if early_response is not None:

            return early_response



        if cmd_name is None:

            # Not a command ??try natural language routing before falling back

            nl_result = await self._try_nl_routing(message)

            if nl_result is not None:

                return nl_result

            # No NL match ??check if @mentioned for a help hint

            if message.mentioned:

                return BotResponse.text_response(

                    "안녕하세요. 주식 분석 도우미입니다.\n"

                    f"Send `{self.command_prefix}help` to view available commands."

                )

            # feiminglingxiaoxi竊똟uchuli

            return BotResponse.text_response("")



        if command is None:

            return BotResponse.error_response("minglingzhixingshibai")



        # 6. zhixingmingling

        try:

            response = await command.execute_async(message, args)

            logger.info(f"[Dispatcher] mingling {cmd_name} zhixingchenggong")

            return response

        except Exception as e:

            logger.error(f"[Dispatcher] mingling {cmd_name} zhixingshibai: {e}")

            logger.exception(e)

            return BotResponse.error_response(f"minglingzhixingshibai: {str(e)[:100]}")



    def set_help_command_getter(self, getter: Callable) -> None:

        """

        shezhibangzhuminglingdeminglingliebiaohuoquqi



        yongyurang HelpCommand huoquminglingliebiao??


        Args:

            getter: huidiaohanshu竊똣anhuiminglingliebiao

        """

        self._help_command_getter = getter



    # ------------------------------------------------------------------ #

    #  Natural language routing (LLM-based)                              #

    # ------------------------------------------------------------------ #



    # Lightweight intent-parsing prompt.  Asks the LLM to output a small

    # JSON object so we can route to the right command.

    _NL_PARSE_PROMPT = """\"

You are a stock analysis assistant router.  Given a user's natural-language

message, determine whether it contains a stock-analysis request.



Return a JSON object (and NOTHING else) with these fields:

- "intent": one of "analysis", "chat", "none"

  * "analysis" ??the user wants stock analysis / diagnosis / comparison

  * "chat" ??the user is asking a general question related to finance

  * "none" ??the message is irrelevant or you are unsure

- "codes": a list of stock codes mentioned (may be empty).

  Format: A-share 6-digit ("600519"), HK with prefix ("hk00700"), US ticker uppercase ("AAPL").

- "strategy": strategy/technique name if the user specified one, else null.

  e.g. "chanlun", "MACD", "qushigenzong", "chan_theory", etc.



Examples:

User: "bangwoanalysisyixia600519he000858"

{"intent":"analysis","codes":["600519","000858"],"strategy":null}



User: "yongchanlunkankanAAPL"

{"intent":"analysis","codes":["AAPL"],"strategy":"chanlun"}



User: "jintiandapanzenmeyang"

{"intent":"chat","codes":[],"strategy":null}



User: "mingtiantianqiruhe"

{"intent":"none","codes":[],"strategy":null}



User: "600519"

{"intent":"analysis","codes":["600519"],"strategy":null}



User: "bangwoanalysisSamsung"

{"intent":"analysis","codes":[],"strategy":null}



User: "analyze TSLA and NVDA using trend strategy"

{"intent":"analysis","codes":["TSLA","NVDA"],"strategy":"trend"}

"""



    # Cheap pre-filter: only invoke LLM when the message plausibly contains

    # stock-related content.  This regex checks for:

    #   - 6-digit A-share / BSE codes (0/3/6 and 43/83/87/88/92 prefixes)

    #   - HK codes like hk00700

    #   - 2-5 uppercase ASCII letters (US tickers)

    #   - Common finance/analysis keywords (Chinese and English)

    _NL_PREFILTER = re.compile(

        r'(?:[036]\d{5}|(?:43|83|87|88|92)\d{4})'  # A-share / BSE 6-digit codes

        r'|(?:hk|HK)\d{5}'                    # HK code

        r'|(?<![a-zA-Z])[A-Z]{2,5}(?![a-zA-Z])'  # US ticker ??UPPERCASE only, no IGNORECASE

        r'|analysis|kankan|chayi?xia|yanjiu|zhenduan|zenmeyang|zoushi|qushi'

        r'|nengmai|keyimai|zhanghaishidie|zenmekan|nengzhui|jianyi|mubiaojia'

        r'|zhicheng|yali|zuli|zhisun|maidian|maidian|jishumian|jibenmian|chouma'

        r'|(?i:analyz|stock|buy|sell|trend|backtest|strateg)',

    )



    _NL_NAME_CLEANUP_PATTERNS = (

        r"""[!"'()\[\]{}<>]+""",

        r'(?i:\b(?:please|analy[sz]e|analysis|research|check|look\s+at|stock|ticker|trend|price)\b)',

        r'(?:bangwo|bangmang|mafan|qing|xiangqingni|woxiang|xiang|yong|anzhao|jiyu|guanyu|dui)\s*',

        r'(?:analysis|kankan|yanjiu|zhenduan|chayi?xia|liaoliao|shuoshuo|wenwen|pinggu)\s*',

        r'(?:zuijin|jinqi|dangqian|jintian|zhezhi|zhege|gegu|stock)\s*',

        r'(?:zoushi|qingkuang|biaoxian|ruhe|zenmeyang|zenmekan|keyima|nengmaima|zhibuzhidemai|jishumian|jibenmian|celve)\s*',

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



        # Layer 1: cheap pre-filter ??skip obviously irrelevant messages

        if not self._passes_nl_prefilter(text):

            return None



        # Layer 2: LLM intent parsing ??extract codes, intent, strategy

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



        # "chat" intent ??route to /chat with original text

        if intent == "chat":

            chat_cmd = self.get_command("chat")

            if chat_cmd:

                logger.info("[Dispatcher] NL routing ??/chat: %s", text[:60])

                return await chat_cmd.execute_async(message, [text])

            return None



        # "analysis" intent ??route to /ask

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

                "[Dispatcher] NL routing ??/ask %s (strategy=%s, text=%s)",

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

                logger.info("[Dispatcher] NL routing ??/chat: %s", text[:60])

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

                "[Dispatcher] NL routing ??/ask %s (strategy=%s, text=%s)",

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

            cleaned = cleaned.strip(" de").strip()

            if cleaned and cleaned not in candidates:

                candidates.append(cleaned)



            for source in list(candidates):

                for token in re.findall(r'[A-Za-z][A-Za-z0-9\.]{0,9}|[\u4e00-\u9fff]{2,12}', source):

                    normalized = token.strip(" de").strip()

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





# quanjufenfaqishili

_dispatcher: Optional[CommandDispatcher] = None





def get_dispatcher() -> CommandDispatcher:

    """

    huoququanjufenfaqishili



    shiyongdanlimoshi竊똲houcidiaoyongshizidongchushihuabingzhucesuoyoumingling??
    """

    global _dispatcher



    if _dispatcher is None:

        from src.config import get_config



        config = get_config()



        # chuangjianfenfaqi

        _dispatcher = CommandDispatcher(

            command_prefix=getattr(config, 'bot_command_prefix', '/'),

            rate_limit_requests=getattr(config, 'bot_rate_limit_requests', 10),

            rate_limit_window=getattr(config, 'bot_rate_limit_window', 60),

            admin_users=getattr(config, 'bot_admin_users', []),

        )



        # zidongzhucesuoyoumingling

        from bot.commands import ALL_COMMANDS

        for command_class in ALL_COMMANDS:

            _dispatcher.register_class(command_class)



        logger.info(f"[Dispatcher] chushihuawancheng竊똹izhuce {len(_dispatcher._commands)} gemingling")



    return _dispatcher





def reset_dispatcher() -> None:

    """Reset the global dispatcher, mainly for tests."""

    global _dispatcher

    _dispatcher = None


