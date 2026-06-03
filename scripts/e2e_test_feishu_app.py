#!/usr/bin/env python3
"""
Feishu App Bot setup validation and live-send smoke test.

Usage:
    ssh <host> "python3 /path/to/e2e_test_feishu_app.py"

Requires FEISHU_APP_ID and FEISHU_APP_SECRET env vars set on the target host.
Optionally set FEISHU_CHAT_ID to send a live test message via interactive card.
Optionally set FEISHU_OPEN_ID to send a live P2P test message (overrides CHAT_ID).
Optionally set FEISHU_TEST_SEND_TEXT=1 to test plain-text-only delivery.
Optionally set FEISHU_DOMAIN to "lark" for international (Lark) tenants.
"""
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("e2e")

# 1. Check credentials
app_id = os.getenv("FEISHU_APP_ID", "").strip()
app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
if not app_id or not app_secret:
    logger.error("Missing FEISHU_APP_ID or FEISHU_APP_SECRET")
    sys.exit(1)

# 2. Try getting tenant_access_token
import requests

resp = requests.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    json={"app_id": app_id, "app_secret": app_secret},
    timeout=30,
)
token_data = resp.json()
if token_data.get("code") != 0:
    logger.error("Failed to get tenant_token: %s", token_data)
    sys.exit(1)

token = token_data["tenant_access_token"]
logger.info("token obtained OK")

# 3. List chats (groups) to find available chat_ids
chats_resp = requests.get(
    "https://open.feishu.cn/open-apis/im/v1/chats?page_size=20",
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
chats_data = chats_resp.json()
logger.info("chats API response code=%s", chats_data.get("code"))
if chats_data.get("code") == 0:
    items = chats_data.get("data", {}).get("items", [])
    logger.info("Found %d chats:", len(items))
    for chat in items:
        logger.info(
            "  chat_id=%s name=%s type=%s",
            chat.get("chat_id"), chat.get("name"), chat.get("chat_type"),
        )
else:
    logger.warning("chat list failed (may lack im:chat permission): %s", chats_data)
    logger.warning("Trying /bot/v3/info instead...")

# 4. Import lark-oapi SDK (must be installed manually)
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
    )
except ImportError:
    logger.error(
        "lark-oapi is NOT installed. Install it manually before running this test:\n"
        "    pip install lark-oapi"
    )
    sys.exit(1)

# 5. Verify SDK client initialisation
bot_resp = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
logger.info("lark-oapi SDK client init OK")
logger.info("E2E setup verification passed.")

# 6. Live send test
_chat_id = os.getenv("FEISHU_CHAT_ID", "").strip()
_open_id = os.getenv("FEISHU_OPEN_ID", "").strip()
_test_text_only = os.getenv("FEISHU_TEST_SEND_TEXT", "").strip() == "1"
_domain = os.getenv("FEISHU_DOMAIN", "feishu").strip().lower()

_receive_id_type = "chat_id"
_receive_id = _chat_id

if _open_id:
    _receive_id_type = "open_id"
    _receive_id = _open_id
    logger.info("FEISHU_OPEN_ID=%s will send P2P message", _open_id)

if _receive_id:
    logger.info("FEISHU_CHAT_ID=%s, performing live send test...", _receive_id)

    # Add project root to path so source imports resolve
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from src.notification_sender.feishu_sender import FeishuSender
    from src.config import Config

    config = Config()
    config.feishu_app_id = app_id
    config.feishu_app_secret = app_secret
    config.feishu_chat_id = _receive_id
    config.feishu_receive_id_type = _receive_id_type
    config.feishu_domain = _domain

    sender = FeishuSender(config)

    # Interactive-card send (default FeishuSender path: card-first, text-fallback)
    ok_card = sender.send_to_feishu(
        "**E2E Test Message**\n\n"
        "This is an automated test from `e2e_test_feishu_app.py`\n"
        f"(mode: {_receive_id_type}{', text-only' if _test_text_only else ''})."
    )
    if ok_card:
        logger.info("Live send test PASSED (via card or text fallback).")
    else:
        logger.error("Live send test FAILED — check FEISHU_CHAT_ID and bot permissions.")
        sys.exit(1)

    # Text-only send (bypasses card construction)
    if _test_text_only:
        import lark_oapi as _lark2
        client = _lark2.Client.builder().app_id(app_id).app_secret(app_secret).domain(
            _lark2.core.const.FEISHU_DOMAIN if _domain == "feishu" else _lark2.core.const.LARK_DOMAIN
        ).build()
        text_json = json.dumps({"text": "**E2E Plain Text Test**\n\nFrom `e2e_test_feishu_app.py` (text-only mode)."}, ensure_ascii=False)
        ok_text = sender._app_send_raw(client, "text", text_json)
        if ok_text:
            logger.info("Text-only send PASSED.")
        else:
            logger.warning("Text-only send FAILED (card path already succeeded).")
else:
    logger.info(
        "Neither FEISHU_CHAT_ID nor FEISHU_OPEN_ID set; skipping live send. "
        "Set FEISHU_CHAT_ID or FEISHU_OPEN_ID to test actual message delivery."
    )
