#!/usr/bin/env python3
"""
Server-side e2e test for Feishu App Bot sender.

Usage:
    ssh <host> "python3 /path/to/e2e_test_feishu_app.py"

Requires FEISHU_APP_ID, FEISHU_APP_SECRET env vars set on the target host.
Optionally set FEISHU_CHAT_ID to send a live test message.
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

# 6. Live send test (only when FEISHU_CHAT_ID is set)
chat_id = os.getenv("FEISHU_CHAT_ID", "").strip()
if chat_id:
    logger.info("FEISHU_CHAT_ID=%s, performing live send test...", chat_id)

    # Add project root to path so source imports resolve
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from src.notification_sender.feishu_sender import FeishuSender
    from src.config import Config

    config = Config()
    config.feishu_app_id = app_id
    config.feishu_app_secret = app_secret
    config.feishu_chat_id = chat_id

    sender = FeishuSender(config)
    ok = sender.send_to_feishu(
        "**E2E Test Message**\n\n"
        "This is an automated test from `e2e_test_feishu_app.py`."
    )
    if ok:
        logger.info("Live send test PASSED.")
    else:
        logger.error("Live send test FAILED — check FEISHU_CHAT_ID and bot permissions.")
        sys.exit(1)
else:
    logger.info(
        "FEISHU_CHAT_ID not set; skipping live send. "
        "Set FEISHU_CHAT_ID to test actual message delivery."
    )
