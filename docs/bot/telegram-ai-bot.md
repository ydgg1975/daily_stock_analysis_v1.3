# Telegram AI 对话 Bot

GitHub Actions 只能定时生成并发送报告，不能持续接收 Telegram 回复。要在 Telegram 里收到报告后直接追问 AI，需要额外运行一个常驻进程：

```powershell
python scripts\telegram_ai_bot.py
```

## 必要配置

复用已有 Telegram 通知配置：

```powershell
$env:TELEGRAM_BOT_TOKEN="你的 Bot Token"
$env:TELEGRAM_CHAT_ID="你的 chat id"
$env:GEMINI_API_KEY="你的 Gemini Key"
```

脚本会默认启用：

```powershell
AGENT_MODE=true
AGENT_NL_ROUTING=true
```

如果要允许多个 Telegram 会话使用，用逗号配置白名单：

```powershell
$env:TELEGRAM_ALLOWED_CHAT_IDS="123456789,-1001234567890"
```

## 用法

直接发命令：

```text
/ask 920402
/chat 920402 现在最大的风险是什么？
/history
/strategies
```

收到股票报告后，直接回复那条报告并提问：

```text
这个还能拿吗？
```

Bot 会把被回复的报告作为上下文交给 `/chat`，并尽量从报告里提取股票代码。

## 部署要点

- 这个脚本必须运行在 VPS、本机、NAS、Railway、Render、Fly.io 等能常驻的环境。
- 不要放在 GitHub Actions 里运行；Actions 任务结束后就无法继续接收 Telegram 消息。
- 默认只允许 `TELEGRAM_CHAT_ID` 或 `TELEGRAM_ALLOWED_CHAT_IDS` 里的会话使用，避免 Bot Token 泄露后被陌生人调用。
- 如果之前设置过 Telegram webhook，脚本启动时会默认调用 `deleteWebhook`，改用 long polling。
