# -*- coding: utf-8 -*-
"""Telegram long-polling entrypoint for the stock AI bot.

This script is intentionally separate from the daily GitHub Actions workflow:
Actions can send reports, but Telegram conversations need a long-running
process that keeps receiving updates.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import logging
import os
import re
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.name_to_code_resolver import find_stock_reference


logger = logging.getLogger("telegram_ai_bot")

MAX_TELEGRAM_TEXT_LEN = 4096
SAFE_CHUNK_LEN = 3800
REPORT_CONTEXT_LEN = 2800
TELEGRAM_IMAGE_MAX_BYTES = 20 * 1024 * 1024
SUPPORTED_TELEGRAM_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

SUPPORTED_COMMANDS = {
    "ask",
    "chat",
    "history",
    "strategies",
    "research",
    "analyze",
    "market",
    "batch",
    "help",
    "status",
    "start",
}

STOCK_CODE_RE = re.compile(
    r"(?<!\d)(?:[036]\d{5}|(?:43|83|87|88|92)\d{4})(?!\d)"
    r"|(?i:HK\d{5})"
)
PAREN_CODE_RE = re.compile(
    r"[（(]\s*((?:[036]\d{5}|(?:43|83|87|88|92)\d{4})|(?i:HK\d{5}))\s*[）)]"
)


@dataclass(frozen=True)
class TelegramIdentity:
    bot_id: int
    username: str


@dataclass(frozen=True)
class PreparedMessage:
    text: str
    mentioned: bool
    should_dispatch: bool
    reason: str


@dataclass(frozen=True)
class TelegramImagePayload:
    file_id: str
    mime_type: str
    file_size: Optional[int] = None
    file_name: str = ""


def _split_csv(value: Optional[str]) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def get_allowed_chat_ids_from_env() -> set[str]:
    """Return chat ids allowed to use this bot.

    TELEGRAM_ALLOWED_CHAT_IDS can contain multiple comma-separated ids.
    TELEGRAM_CHAT_ID is used as the single-chat fallback, matching the existing
    notification sender configuration.
    """

    allowed = _split_csv(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS"))
    if not allowed:
        allowed = _split_csv(os.getenv("TELEGRAM_CHAT_ID"))
    return allowed


def extract_text(message: dict[str, Any]) -> str:
    return str(message.get("text") or message.get("caption") or "").strip()


def extract_image_payload(message: dict[str, Any]) -> Optional[TelegramImagePayload]:
    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        candidates = [item for item in photos if isinstance(item, dict) and item.get("file_id")]
        if candidates:
            best = max(candidates, key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0))
            file_size = best.get("file_size")
            return TelegramImagePayload(
                file_id=str(best["file_id"]),
                mime_type="image/jpeg",
                file_size=int(file_size) if isinstance(file_size, int) else None,
                file_name="telegram-photo.jpg",
            )

    document = message.get("document")
    if isinstance(document, dict) and document.get("file_id"):
        mime_type = str(document.get("mime_type") or "").split(";")[0].strip().lower()
        if mime_type in SUPPORTED_TELEGRAM_IMAGE_MIME_TYPES:
            file_size = document.get("file_size")
            return TelegramImagePayload(
                file_id=str(document["file_id"]),
                mime_type=mime_type,
                file_size=int(file_size) if isinstance(file_size, int) else None,
                file_name=str(document.get("file_name") or "telegram-image"),
            )

    return None


def _command_name(text: str) -> Optional[str]:
    match = re.match(r"^/([A-Za-z0-9_]+)(?:@[A-Za-z0-9_]+)?(?:\s|$)", text.strip())
    if not match:
        return None
    return match.group(1).lower()


def normalize_command_mention(text: str, bot_username: str) -> str:
    """Turn /ask@MyBot into /ask for the existing dispatcher."""

    if not bot_username:
        return text
    return re.sub(
        rf"^/([A-Za-z0-9_]+)@{re.escape(bot_username)}(?=\s|$)",
        r"/\1",
        text.strip(),
        flags=re.IGNORECASE,
    )


def strip_plain_mention(text: str, bot_username: str) -> str:
    if not bot_username:
        return text
    return re.sub(rf"@{re.escape(bot_username)}\b", "", text, flags=re.IGNORECASE).strip()


def is_reply_to_bot(message: dict[str, Any], bot_id: int) -> bool:
    reply = message.get("reply_to_message")
    if not isinstance(reply, dict):
        return False
    sender = reply.get("from")
    return isinstance(sender, dict) and sender.get("id") == bot_id


def extract_stock_code(text: str) -> Optional[str]:
    """Best-effort extraction from a rendered stock report."""

    if not text:
        return None

    head = text[:1200]
    paren_match = PAREN_CODE_RE.search(head)
    if paren_match:
        return paren_match.group(1).upper()

    code_match = STOCK_CODE_RE.search(head)
    if code_match:
        return code_match.group(0).upper()

    return None


def build_reply_chat_prompt(question: str, replied_text: str) -> str:
    """Convert a free-form reply to a stock report into a /chat command."""

    code = extract_stock_code(replied_text)
    compact_report = replied_text.strip()
    if len(compact_report) > REPORT_CONTEXT_LEN:
        compact_report = compact_report[:REPORT_CONTEXT_LEN].rstrip() + "\n...（报告已截断）"

    code_line = f"股票代码：{code}\n" if code else ""
    return (
        "/chat 用户正在回复一条股票分析报告。请基于报告上下文回答追问，"
        "不要把报告当成实时行情，必要时说明仍需以最新盘口为准。\n"
        f"{code_line}"
        f"报告上下文：\n{compact_report}\n\n"
        f"用户追问：{question.strip()}"
    )


def build_direct_stock_question_command(text: str) -> Optional[str]:
    """Turn a private natural-language stock question into a deterministic /ask."""

    normalized = str(text or "").strip()
    if not normalized:
        return None

    try:
        reference = find_stock_reference(normalized)
    except Exception as exc:
        logger.debug("stock reference extraction failed: %s", exc)
        return None

    if not reference:
        return None

    code, matched_text = reference
    question = normalized.replace(matched_text, "", 1).strip()
    question = re.sub(r"^(请|帮我|帮忙|麻烦|分析|看看|看一下|查一下|问一下)\s*", "", question)
    question = question.strip(" ，,。.!！?？")
    return f"/ask {code} {question}".strip()


def build_image_stock_question_command(
    caption: str,
    items: list[tuple[str, Optional[str], str]],
    bot_username: str = "",
) -> Optional[str]:
    """Build a deterministic /ask command from image-extracted stock items."""

    seen: set[str] = set()
    codes: list[str] = []
    for code, _name, _confidence in items:
        normalized = str(code or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            codes.append(normalized)

    if not codes:
        return None

    clean_caption = strip_plain_mention(caption.strip(), bot_username)
    clean_caption = normalize_command_mention(clean_caption, bot_username)
    clean_caption = re.sub(r"^/(ask|analyze|chat)(?:@[A-Za-z0-9_]+)?\b", "", clean_caption, flags=re.IGNORECASE)
    clean_caption = clean_caption.strip(" ，,。.!！?？")
    if not clean_caption:
        clean_caption = "根据图片截图分析"

    return f"/ask {','.join(codes[:5])} {clean_caption}".strip()


def build_image_no_stock_response(raw_text: str, provider: str) -> str:
    snippet = (raw_text or "").strip()
    if len(snippet) > 1000:
        snippet = snippet[:1000].rstrip() + "\n...（图片理解结果已截断）"
    if snippet:
        return (
            f"我看到了图片，但没有识别到股票代码。\n\n"
            f"图片理解来源：{provider}\n"
            f"{snippet}\n\n"
            "请补充股票代码，或重新发送包含股票代码/名称的截图。"
        )
    return "我看到了图片，但没有识别到股票代码。请补充股票代码，或重新发送包含股票代码/名称的截图。"


def prepare_message(message: dict[str, Any], identity: TelegramIdentity) -> PreparedMessage:
    raw_text = extract_text(message)
    if not raw_text:
        return PreparedMessage("", False, False, "empty")

    normalized = normalize_command_mention(raw_text, identity.username)
    mentioned = raw_text != normalized

    if identity.username and re.search(rf"@{re.escape(identity.username)}\b", normalized, re.IGNORECASE):
        mentioned = True
        normalized = strip_plain_mention(normalized, identity.username)

    chat = message.get("chat") or {}
    chat_type = str(chat.get("type") or "")
    is_private = chat_type == "private"
    replied_to_bot = is_reply_to_bot(message, identity.bot_id)

    command = _command_name(normalized)
    if command == "start":
        normalized = "/help"
        command = "help"

    if command:
        should_dispatch = command in SUPPORTED_COMMANDS
        return PreparedMessage(normalized, True, should_dispatch, f"command:{command}")

    reply = message.get("reply_to_message")
    if isinstance(reply, dict) and replied_to_bot:
        replied_text = extract_text(reply)
        if replied_text:
            prompt = build_reply_chat_prompt(normalized, replied_text)
            return PreparedMessage(prompt, True, True, "reply-report")

    if is_private or mentioned:
        direct_stock_command = build_direct_stock_question_command(normalized)
        if direct_stock_command:
            return PreparedMessage(direct_stock_command, True, True, "stock-question")

    if is_private:
        return PreparedMessage(normalized, True, True, "private-nl")

    if mentioned:
        return PreparedMessage(normalized, True, True, "mentioned-nl")

    return PreparedMessage(normalized, False, False, "ignored-group-message")


def to_bot_message(message: dict[str, Any], prepared: PreparedMessage):
    from bot.models import BotMessage, ChatType

    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    raw_chat_type = str(chat.get("type") or "")
    if raw_chat_type == "private":
        chat_type = ChatType.PRIVATE
    elif raw_chat_type in {"group", "supergroup"}:
        chat_type = ChatType.GROUP
    else:
        chat_type = ChatType.UNKNOWN

    timestamp = datetime.fromtimestamp(message.get("date", time.time()))
    username = sender.get("username") or sender.get("first_name") or str(sender.get("id") or "unknown")

    return BotMessage(
        platform="telegram",
        message_id=str(message.get("message_id") or ""),
        user_id=str(sender.get("id") or ""),
        user_name=str(username),
        chat_id=str(chat.get("id") or ""),
        chat_type=chat_type,
        content=prepared.text,
        raw_content=extract_text(message),
        mentioned=prepared.mentioned,
        timestamp=timestamp,
        raw_data=message,
    )


def chunk_text(text: str, limit: int = SAFE_CHUNK_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return chunks


def format_telegram_text(text: str) -> str:
    """Convert common Markdown-ish agent output into readable Telegram plain text."""

    result = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not result:
        return ""

    result = re.sub(r"```(?:\w+)?\n?", "", result)
    result = re.sub(r"^#{1,6}\s*", "", result, flags=re.MULTILINE)
    result = re.sub(r"^\s*[-*]\s+", "• ", result, flags=re.MULTILINE)
    result = re.sub(r"\*\*([^*\n]+?)\*\*", r"\1", result)
    result = re.sub(r"__([^_\n]+?)__", r"\1", result)
    result = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", result)
    result = result.replace("`", "")
    result = re.sub(r"[ \t]+\n", "\n", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


class TelegramPollingBot:
    def __init__(
        self,
        token: str,
        allowed_chat_ids: Iterable[str],
        poll_timeout: int = 30,
        request_timeout: int = 45,
        delete_webhook: bool = True,
        allow_all_chats: bool = False,
    ):
        self.token = token
        self.allowed_chat_ids = {str(chat_id) for chat_id in allowed_chat_ids if str(chat_id).strip()}
        self.poll_timeout = poll_timeout
        self.request_timeout = request_timeout
        self.delete_webhook = delete_webhook
        self.allow_all_chats = allow_all_chats
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()
        self._stopped = False
        self.identity = self._get_identity()

        if not self.allowed_chat_ids and not self.allow_all_chats:
            raise ValueError(
                "未配置 Telegram 聊天白名单。请设置 TELEGRAM_CHAT_ID 或 TELEGRAM_ALLOWED_CHAT_IDS。"
            )

    def stop(self, *_args: object) -> None:
        self._stopped = True

    def _api(self, method: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/{method}",
            json=payload or {},
            timeout=self.request_timeout,
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise RuntimeError(f"Telegram API returned non-JSON response for {method}")

        if response.status_code != 200 or not data.get("ok"):
            description = data.get("description") or response.text[:200]
            raise RuntimeError(f"Telegram API {method} failed: {description}")

        return data

    def _get_identity(self) -> TelegramIdentity:
        data = self._api("getMe")
        result = data.get("result") or {}
        username = str(result.get("username") or "")
        bot_id = int(result.get("id") or 0)
        logger.info("Telegram bot ready: @%s (%s)", username, bot_id)
        return TelegramIdentity(bot_id=bot_id, username=username)

    def _delete_webhook_if_needed(self) -> None:
        if not self.delete_webhook:
            return
        self._api("deleteWebhook", {"drop_pending_updates": False})
        logger.info("Telegram webhook disabled for long polling")

    def _send_chat_action(self, chat_id: str, action: str = "typing", message_thread_id: Optional[int] = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "action": action}
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        try:
            self._api("sendChatAction", payload)
        except Exception as exc:
            logger.debug("sendChatAction failed: %s", exc)

    @contextmanager
    def typing_indicator(self, chat_id: str, message_thread_id: Optional[int] = None):
        """Keep Telegram's typing indicator alive while a long command runs."""

        stop_event = threading.Event()

        def _worker() -> None:
            while not stop_event.is_set():
                self._send_chat_action(chat_id, message_thread_id=message_thread_id)
                stop_event.wait(4.0)

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop_event.set()
            worker.join(timeout=0.2)

    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to_message_id: Optional[int] = None,
        message_thread_id: Optional[int] = None,
    ) -> None:
        text = format_telegram_text(text)
        if not text.strip():
            return

        for index, chunk in enumerate(chunk_text(text)):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk[:MAX_TELEGRAM_TEXT_LEN],
                "disable_web_page_preview": True,
            }
            if index == 0 and reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id
                payload["allow_sending_without_reply"] = True
            if message_thread_id is not None:
                payload["message_thread_id"] = message_thread_id
            self._api("sendMessage", payload)

    def _is_allowed(self, chat_id: str) -> bool:
        return self.allow_all_chats or chat_id in self.allowed_chat_ids

    def _get_updates(self, offset: Optional[int]) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": self.poll_timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        data = self._api("getUpdates", payload)
        result = data.get("result") or []
        return result if isinstance(result, list) else []

    def _download_telegram_file(self, payload: TelegramImagePayload) -> bytes:
        if payload.file_size and payload.file_size > TELEGRAM_IMAGE_MAX_BYTES:
            raise ValueError(f"图片过大，最大支持 {TELEGRAM_IMAGE_MAX_BYTES // (1024 * 1024)}MB")

        file_data = self._api("getFile", {"file_id": payload.file_id}).get("result") or {}
        file_path = str(file_data.get("file_path") or "")
        if not file_path:
            raise RuntimeError("Telegram 未返回 file_path")

        response = self.session.get(
            f"https://api.telegram.org/file/bot{self.token}/{file_path}",
            stream=True,
            timeout=self.request_timeout,
        )
        response.raise_for_status()

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > TELEGRAM_IMAGE_MAX_BYTES:
                raise ValueError(f"图片过大，最大支持 {TELEGRAM_IMAGE_MAX_BYTES // (1024 * 1024)}MB")
            chunks.append(chunk)
        return b"".join(chunks)

    def _should_handle_image_message(self, message: dict[str, Any], chat_type: str) -> bool:
        if chat_type == "private":
            return True
        if is_reply_to_bot(message, self.identity.bot_id):
            return True
        caption = extract_text(message)
        if not caption:
            return False
        normalized = normalize_command_mention(caption, self.identity.username)
        if _command_name(normalized):
            return True
        return bool(
            self.identity.username
            and re.search(rf"@{re.escape(self.identity.username)}\b", caption, re.IGNORECASE)
        )

    def _handle_image_message(
        self,
        message: dict[str, Any],
        payload: TelegramImagePayload,
        chat_id: str,
        message_id: Optional[int],
        thread_id: Optional[int],
    ) -> bool:
        chat = message.get("chat") or {}
        chat_type = str(chat.get("type") or "")
        if not self._should_handle_image_message(message, chat_type):
            logger.debug("Ignored Telegram image without private chat, mention, reply, or command")
            return True

        try:
            with self.typing_indicator(chat_id, message_thread_id=thread_id):
                image_bytes = self._download_telegram_file(payload)
                from src.services.telegram_image_stock_analyzer import analyze_stock_image_bytes

                analysis = analyze_stock_image_bytes(image_bytes, payload.mime_type)
                command = build_image_stock_question_command(
                    extract_text(message),
                    analysis.items,
                    self.identity.username,
                )
                if not command:
                    response_text = build_image_no_stock_response(analysis.raw_text, analysis.provider)
                    self.send_message(
                        chat_id,
                        response_text,
                        reply_to_message_id=message_id,
                        message_thread_id=thread_id,
                    )
                    return True

                prepared = PreparedMessage(command, True, True, "image-stock-question")
                bot_message = to_bot_message(message, prepared)

                from bot.dispatcher import get_dispatcher

                response = get_dispatcher().dispatch(bot_message)

            if response.text.strip():
                self.send_message(
                    chat_id,
                    response.text,
                    reply_to_message_id=message_id,
                    message_thread_id=thread_id,
                )
            return True
        except Exception as exc:
            logger.error("Telegram image handling failed: %s", exc)
            logger.debug("Image handling error details", exc_info=True)
            self.send_message(
                chat_id,
                f"图片处理失败：{exc}",
                reply_to_message_id=message_id,
                message_thread_id=thread_id,
            )
            return True

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return

        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        message_id = message.get("message_id")
        thread_id = message.get("message_thread_id")

        if not self._is_allowed(chat_id):
            logger.warning("Ignored unauthorized Telegram chat_id=%s", chat_id)
            return

        image_payload = extract_image_payload(message)
        if image_payload and self._handle_image_message(message, image_payload, chat_id, message_id, thread_id):
            return

        prepared = prepare_message(message, self.identity)
        if not prepared.should_dispatch:
            logger.debug("Ignored Telegram message: %s", prepared.reason)
            if prepared.reason.startswith("command:"):
                self.send_message(
                    chat_id,
                    "这个命令还没接入。可用：/ask、/chat、/history、/strategies、/research、/help、/status。",
                    reply_to_message_id=message_id,
                    message_thread_id=thread_id,
                )
            return

        bot_message = to_bot_message(message, prepared)

        from bot.dispatcher import get_dispatcher

        with self.typing_indicator(chat_id, message_thread_id=thread_id):
            response = get_dispatcher().dispatch(bot_message)
        if response.text.strip():
            self.send_message(
                chat_id,
                response.text,
                reply_to_message_id=message_id,
                message_thread_id=thread_id,
            )

    def run_forever(self) -> None:
        self._delete_webhook_if_needed()
        offset: Optional[int] = None
        logger.info(
            "Listening for Telegram messages. allowed_chat_ids=%s",
            ",".join(sorted(self.allowed_chat_ids)) if self.allowed_chat_ids else "ALL",
        )

        while not self._stopped:
            try:
                updates = self._get_updates(offset)
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        offset = update_id + 1
                    self.handle_update(update)
            except KeyboardInterrupt:
                self.stop()
            except Exception as exc:
                logger.error("Telegram polling loop error: %s", exc)
                logger.debug("Polling error details", exc_info=True)
                time.sleep(5)


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Telegram AI conversation bot.")
    parser.add_argument("--poll-timeout", type=int, default=int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30")))
    parser.add_argument("--request-timeout", type=int, default=int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "45")))
    parser.add_argument(
        "--no-delete-webhook",
        action="store_true",
        help="Do not call deleteWebhook before polling.",
    )
    return parser.parse_args()


def configure_runtime_defaults() -> None:
    load_dotenv(ROOT / ".env", override=False)

    # The interactive Telegram bot should expose the project's AI commands by
    # default; users can still override either value explicitly.
    os.environ.setdefault("AGENT_MODE", "true")
    os.environ.setdefault("AGENT_NL_ROUTING", "true")


def main() -> int:
    configure_runtime_defaults()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("缺少 TELEGRAM_BOT_TOKEN。")
        return 2

    delete_webhook = _truthy_env("TELEGRAM_POLLING_DELETE_WEBHOOK", True) and not args.no_delete_webhook
    allow_all_chats = _truthy_env("TELEGRAM_ALLOW_ALL_CHATS", False)

    try:
        bot = TelegramPollingBot(
            token=token,
            allowed_chat_ids=get_allowed_chat_ids_from_env(),
            poll_timeout=args.poll_timeout,
            request_timeout=args.request_timeout,
            delete_webhook=delete_webhook,
            allow_all_chats=allow_all_chats,
        )
    except Exception as exc:
        logger.error("Telegram AI Bot 启动失败: %s", exc)
        return 2

    signal.signal(signal.SIGINT, bot.stop)
    signal.signal(signal.SIGTERM, bot.stop)
    bot.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
