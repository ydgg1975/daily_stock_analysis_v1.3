# Complete Configuration & Deployment Guide

This document contains the complete configuration guide for the AI Stock Analysis System, intended for users who need advanced features or special deployment methods.

> Quick start guide available in [README_EN.md](README_EN.md). This document covers advanced configuration.

## Project Structure

```
daily_stock_analysis/
├── main.py              # Main entry point
├── src/                 # Core business logic
│   ├── analyzer.py      # AI analyzer
│   ├── config.py        # Configuration management
│   ├── notification.py  # Message push notifications
│   └── ...
├── data_provider/       # Multi-source data adapters
├── bot/                 # Bot interaction module
├── api/                 # FastAPI backend service
├── apps/dsa-web/        # React frontend
├── docker/              # Docker configuration
├── docs/                # Project documentation
└── .github/workflows/   # GitHub Actions
```

## Table of Contents

- [Project Structure](#project-structure)
- [GitHub Actions Configuration](#github-actions-configuration)
- [Complete Environment Variables List](#complete-environment-variables-list)
- [Docker Deployment](#docker-deployment)
- [Local Deployment](#local-deployment)
- [Scheduled Task Configuration](#scheduled-task-configuration)
- [Notification Channel Configuration](#notification-channel-configuration)
- [Data Source Configuration](#data-source-configuration)
- [Advanced Features](#advanced-features)
- [Backtesting](#backtesting)
- [Local WebUI Management Interface](#local-webui-management-interface)

---

## GitHub Actions Configuration

### 1. Fork this Repository

Click the `Fork` button in the upper right corner.

### 2. Configure Secrets

Go to your forked repo → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

<div align="center">
  <img src="../sources/secret_config.png" alt="GitHub Secrets Configuration" width="600">
</div>

#### AI Model Configuration (Choose One)

| Secret Name | Description | Required |
|------------|------|:----:|
| `GEMINI_API_KEY` | Get free key from [Google AI Studio](https://aistudio.google.com/) | ✅* |
| `OPENAI_API_KEY` | OpenAI-compatible API Key (supports DeepSeek, Qwen, etc.) | Optional |
| `OPENAI_BASE_URL` | OpenAI-compatible API endpoint (e.g., `https://api.deepseek.com/v1`) | Optional |
| `OPENAI_MODEL` | Model name (e.g., `deepseek-chat`) | Optional |

> *Note: Configure at least one of `GEMINI_API_KEY` or `OPENAI_API_KEY`

#### Notification Channels (Multiple can be configured, all will receive notifications)

| Secret Name | Description | Required |
|------------|------|:----:|
| `WECHAT_WEBHOOK_URL` | WeChat Work Webhook URL | Optional |
| `FEISHU_WEBHOOK_URL` | Feishu Webhook URL | Optional |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token (get from @BotFather) | Optional |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | Optional |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID (for sending to topics) | Optional |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL ([How to create](https://support.discord.com/hc/en-us/articles/228383668)) | Optional |
| `DISCORD_BOT_TOKEN` | Discord Bot Token (choose one with Webhook) | Optional |
| `DISCORD_MAIN_CHANNEL_ID` | Discord Channel ID (required when using Bot) | Optional |
| `SLACK_BOT_TOKEN` | Slack Bot Token (recommended, supports image upload; takes priority over Webhook when both set) | Optional |
| `SLACK_CHANNEL_ID` | Slack Channel ID (required when using Bot) | Optional |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL (text only, no image support) | Optional |
| `EMAIL_SENDER` | Sender email (e.g., `xxx@qq.com`) | Optional |
| `EMAIL_PASSWORD` | Email authorization code (not login password) | Optional |
| `EMAIL_RECEIVERS` | Receiver emails (comma-separated, leave empty to send to self) | Optional |
| `PUSHPLUS_TOKEN` | PushPlus Token ([Get here](https://www.pushplus.plus), Chinese push service) | Optional |
| `SERVERCHAN3_SENDKEY` | ServerChan v3 Sendkey ([Get here](https://sc3.ft07.com/), mobile app push service) | Optional |
| `CUSTOM_WEBHOOK_URLS` | Custom Webhook (supports DingTalk, etc., comma-separated) | Optional |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | Bearer Token for custom webhooks (for authenticated webhooks) | Optional |
| `WEBHOOK_VERIFY_SSL` | Verify Webhook HTTPS certificates (default true). Set to false for self-signed certs. WARNING: Disabling has serious security risk (MITM), use only on trusted internal networks | Optional |

> *Note: Configure at least one channel; multiple channels will all receive notifications

#### Push Behavior Configuration

| Secret Name | Description | Required |
|------------|------|:----:|
| `SINGLE_STOCK_NOTIFY` | Single stock push mode: set to `true` to push immediately after each stock analysis | Optional |
| `REPORT_TYPE` | Report type: `simple` (concise), `full` (complete), `brief` (3-5 sentences), Docker recommended: `full` | Optional |
| `REPORT_LANGUAGE` | Report output language: `zh` (default Chinese) / `en` (English); also updates prompt instructions, templates, notification fallbacks, and fixed copy in the Web report view | Optional |
| `REPORT_TEMPLATES_DIR` | Jinja2 template directory (relative to project root, default `templates`) | Optional |
| `REPORT_RENDERER_ENABLED` | Enable Jinja2 template rendering (default `false`, zero regression) | Optional |
| `REPORT_INTEGRITY_ENABLED` | Enable report integrity checks, retry or placeholder on missing fields (default `true`) | Optional |
| `REPORT_INTEGRITY_RETRY` | Integrity retry count (default `1`, `0` = placeholder only) | Optional |
| `REPORT_HISTORY_COMPARE_N` | History signal comparison count, `0` off (default), `>0` enable | Optional |
| `ANALYSIS_DELAY` | Delay between stock analysis and market review (seconds) to avoid API rate limits, e.g., `10` | Optional |

#### Other Configuration

| Secret Name | Description | Required |
|------------|------|:----:|
| `STOCK_LIST` | Watchlist codes, e.g., `600519,300750,002594` | ✅ |
| `TAVILY_API_KEYS` | [Tavily](https://tavily.com/) Search API (for news search) | Recommended |
| `MINIMAX_API_KEYS` | [MiniMax](https://platform.minimaxi.com/) Coding Plan Web Search (structured search results) | Optional |
| `BOCHA_API_KEYS` | [Bocha Search](https://open.bocha.cn/) Web Search API (Chinese search optimized, supports AI summaries, multiple keys comma-separated) | Optional |
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis) Backup search | Optional |
| `SEARXNG_BASE_URLS` | SearXNG self-hosted instances (quota-free fallback, enable format: json in settings.yml); when empty the app auto-discovers public instances | Optional |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Auto-discover public SearXNG instances from `searx.space` when `SEARXNG_BASE_URLS` is empty (default `true`) | Optional |
| `TUSHARE_TOKEN` | [Tushare Pro](https://tushare.pro/weborder/#/login?reg=834638) Token | Optional |
| `TICKFLOW_API_KEY` | [TickFlow](https://tickflow.org) API key for CN market review index enhancement; market breadth also uses TickFlow when the plan supports universe queries | Optional |

#### ✅ Minimum Configuration Example

To get started quickly, you need at minimum:

1. **AI Model**: `GEMINI_API_KEY` (recommended) or `OPENAI_API_KEY`
2. **Notification Channel**: At least one, e.g., `WECHAT_WEBHOOK_URL` or `EMAIL_SENDER` + `EMAIL_PASSWORD`
3. **Stock List**: `STOCK_LIST` (required)
4. **Search API**: `TAVILY_API_KEYS` (strongly recommended for news search)

> Configure these 4 items and you're ready to go!

### 3. Enable Actions

1. Go to your forked repository
2. Click the `Actions` tab at the top
3. If prompted, click `I understand my workflows, go ahead and enable them`

### 4. Manual Test

1. Go to `Actions` tab
2. Select `Daily Stock Analysis` workflow on the left
3. Click `Run workflow` button on the right
4. Select run mode
5. Click green `Run workflow` to confirm

### 5. Done!

Default schedule: Every weekday at **18:00 (Beijing Time)** automatic execution.

---

## Complete Environment Variables List

### AI Model Configuration

> Full details: [LLM Config Guide](LLM_CONFIG_GUIDE_EN.md) (three-tier config, channels, Vision, Agent, troubleshooting).

| Variable | Description | Default | Required |
|--------|------|--------|:----:|
| `LITELLM_MODEL` | Primary model, format `provider/model` (e.g. `gemini/gemini-2.5-flash`), recommended | - | No |
| `AGENT_LITELLM_MODEL` | Optional Agent-only primary model; when empty it inherits `LITELLM_MODEL`, and bare names are normalized to `openai/<model>` | - | No |
| `LITELLM_FALLBACK_MODELS` | Fallback models, comma-separated | - | No |
| `LLM_CHANNELS` | Channel names (comma-separated), use with `LLM_{NAME}_*`, see [LLM Config Guide](LLM_CONFIG_GUIDE_EN.md) | - | No |
| `LITELLM_CONFIG` | LiteLLM YAML config path (advanced) | - | No |
| `GEMINI_API_KEY` | Google Gemini API Key | - | Optional |
| `GEMINI_MODEL` | Primary model name (legacy, `LITELLM_MODEL` preferred) | `gemini-3-flash-preview` | No |
| `GEMINI_MODEL_FALLBACK` | Fallback model (legacy) | `gemini-2.5-flash` | No |
| `OPENAI_API_KEY` | OpenAI-compatible API Key | - | Optional |
| `OPENAI_BASE_URL` | OpenAI-compatible API endpoint | - | Optional |
| `OLLAMA_API_BASE` | Ollama local service address (e.g. `http://localhost:11434`), see [LLM Config Guide](LLM_CONFIG_GUIDE_EN.md) | - | Optional |
| `OPENAI_MODEL` | OpenAI model name (legacy) | `gpt-4o` | Optional |

> *Note: Configure at least one of `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_API_BASE`, or `LLM_CHANNELS` / `LITELLM_CONFIG`

### Notification Channel Configuration

| Variable | Description | Required |
|--------|------|:----:|
| `WECHAT_WEBHOOK_URL` | WeChat Work Bot Webhook URL | Optional |
| `FEISHU_WEBHOOK_URL` | Feishu Bot Webhook URL | Optional |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | Optional |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | Optional |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID | Optional |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL | Optional |
| `DISCORD_BOT_TOKEN` | Discord Bot Token (choose one with Webhook) | Optional |
| `DISCORD_MAIN_CHANNEL_ID` | Discord Channel ID (required when using Bot) | Optional |
| `DISCORD_MAX_WORDS` | Discord Word Limit (default 2000 for un-upgraded servers) | Optional |
| `SLACK_BOT_TOKEN` | Slack Bot Token (recommended, supports image upload; takes priority over Webhook when both set) | Optional |
| `SLACK_CHANNEL_ID` | Slack Channel ID (required when using Bot) | Optional |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL (text only, no image support) | Optional |
| `EMAIL_SENDER` | Sender email | Optional |
| `EMAIL_PASSWORD` | Email authorization code (not login password) | Optional |
| `EMAIL_RECEIVERS` | Receiver emails (comma-separated, leave empty to send to self) | Optional |
| `CUSTOM_WEBHOOK_URLS` | Custom Webhook (comma-separated) | Optional |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | Custom Webhook Bearer Token | Optional |
| `WEBHOOK_VERIFY_SSL` | Webhook HTTPS certificate verification (default true). Set to false for self-signed certs. WARNING: Disabling has serious security risk | Optional |
| `PUSHOVER_USER_KEY` | Pushover User Key | Optional |
| `PUSHOVER_API_TOKEN` | Pushover API Token | Optional |
| `PUSHPLUS_TOKEN` | PushPlus Token (Chinese push service) | Optional |
| `SERVERCHAN3_SENDKEY` | ServerChan v3 Sendkey | Optional |

#### Feishu Cloud Document Configuration (Optional, solves message truncation issues)

| Variable | Description | Required |
|--------|------|:----:|
| `FEISHU_APP_ID` | Feishu App ID | Optional |
| `FEISHU_APP_SECRET` | Feishu App Secret | Optional |
| `FEISHU_FOLDER_TOKEN` | Feishu Cloud Drive Folder Token | Optional |

> Feishu Cloud Document setup steps:
> 1. Create an app in [Feishu Developer Console](https://open.feishu.cn/app)
> 2. Configure GitHub Secrets
> 3. Create a group and add the app bot
> 4. Add the group as a collaborator to the cloud drive folder (with manage permissions)

### Search Service Configuration

| Variable | Description | Required |
|--------|------|:----:|
| `TAVILY_API_KEYS` | Tavily Search API Key (recommended) | Recommended |
| `MINIMAX_API_KEYS` | MiniMax Coding Plan Web Search (structured results) | Optional |
| `BOCHA_API_KEYS` | Bocha Search API Key (Chinese optimized) | Optional |
| `BRAVE_API_KEYS` | Brave Search API Key (US stocks optimized) | Optional |
| `SERPAPI_API_KEYS` | SerpAPI Backup search | Optional |
| `SEARXNG_BASE_URLS` | SearXNG self-hosted instances (quota-free fallback, enable format: json in settings.yml); when empty the app auto-discovers public instances | Optional |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Auto-discover public SearXNG instances from `searx.space` when `SEARXNG_BASE_URLS` is empty (default `true`) | Optional |

### Data Source Configuration

| Variable | Description | Default | Required |
|--------|------|--------|:----:|
| `TUSHARE_TOKEN` | Tushare Pro Token | - | Optional |
| `TICKFLOW_API_KEY` | TickFlow API key; CN market review indices prefer TickFlow when configured, and market breadth does so only when the plan supports universe queries | - | Optional |
| `ENABLE_REALTIME_QUOTE` | Enable real-time quotes (if disabled, uses historical closing prices for analysis) | `true` | Optional |
| `ENABLE_REALTIME_TECHNICAL_INDICATORS` | Intraday real-time technicals: Calculate MA5/MA10/MA20 and bull trends using real-time prices when enabled (Issue #234); uses yesterday's close if disabled. | `true` | Optional |
| `ENABLE_CHIP_DISTRIBUTION` | Enable chip distribution analysis (this API is unstable, recommended to disable for cloud deployment). GitHub Actions users must set `ENABLE_CHIP_DISTRIBUTION=true` in Repository Variables to enable; disabled by default in workflows. | `true` | Optional |
| `ENABLE_EASTMONEY_PATCH` | Eastmoney API patch: Recommended to set to `true` when Eastmoney APIs fail frequently (e.g., RemoteDisconnected, connection closed). Injects NID tokens and random User-Agents to reduce rate limiting probability. | `false` | Optional |
| `REALTIME_SOURCE_PRIORITY` | Real-time quote source priority (comma-separated), e.g., `tencent,akshare_sina,efinance,akshare_em` | See .env.example | Optional |
| `ENABLE_FUNDAMENTAL_PIPELINE` | Master switch for fundamental aggregation; when disabled, returns `not_supported` block only, without altering the original analysis pipeline. | `true` | Optional |
| `FUNDAMENTAL_STAGE_TIMEOUT_SECONDS` | Total latency budget for the fundamental stage (seconds) | `1.5` | Optional |
| `FUNDAMENTAL_FETCH_TIMEOUT_SECONDS` | Timeout for a single capability source call (seconds) | `0.8` | Optional |
| `FUNDAMENTAL_RETRY_MAX` | Retry count for fundamental capabilities (including the first attempt) | `1` | Optional |
| `FUNDAMENTAL_CACHE_TTL_SECONDS` | Fundamental aggregation cache TTL (seconds), short cache to reduce repeated API pulling. | `120` | Optional |
| `FUNDAMENTAL_CACHE_MAX_ENTRIES` | Maximum entries for fundamental cache (evicted by time within TTL) | `256` | Optional |

> **Behavior Notes:**
> - **A-shares**: Returns aggregated capabilities by `valuation/growth/earnings/institution/capital_flow/dragon_tiger/boards`.
> - **ETFs**: Returns available items, marks missing capabilities as `not_supported`, and does not affect the original flow overall.
> - **US/HK stocks**: Returns `not_supported` fallback block.
> - Any exception uses fail-open logic, only logs errors without affecting the main technical/news/chip pipeline.
> - **Field contracts**:
>   - `fundamental_context.boards.data` = `sector_rankings` (sector rise/fall leaderboard, structure `{top, bottom}`);
>   - `get_stock_info.belong_boards` = list of sectors the individual stock belongs to;
>   - `get_stock_info.boards` is a compatibility alias, value is identical to `belong_boards` (removal considered only in major version updates);
>   - `get_stock_info.sector_rankings` stays consistent with `fundamental_context.boards.data`.
> - **Sector leaderboard** uses a fixed fallback order: consistent with global priority.
> - **Timeout control** is a `best-effort` soft timeout: the stage will quickly degrade and continue execution based on the budget, but does not guarantee a hard interrupt of underlying third-party network calls.
> - `FUNDAMENTAL_STAGE_TIMEOUT_SECONDS=1.5` indicates the target budget for the newly added fundamental stage, not a strict hard SLA.
> - For a hard SLA, please upgrade to isolated child process execution in future versions to forcefully terminate timeout tasks.

### Other Configuration

| Variable | Description | Default |
|--------|------|--------|
| `STOCK_LIST` | Watchlist codes (comma-separated) | - |
| `MAX_WORKERS` | Concurrent threads | `3` |
| `MARKET_REVIEW_ENABLED` | Enable market review | `true` |
| `MARKET_REVIEW_REGION` | Market review region: cn (A-shares), us (US stocks), both | `cn` |
| `SCHEDULE_ENABLED` | Enable scheduled tasks | `false` |
| `SCHEDULE_TIME` | Scheduled execution time | `18:00` |
| `SCANNER_PROFILE` | Default scanner profile (keep `cn_preopen_v1` for this phase) | `cn_preopen_v1` |
| `SCANNER_SCHEDULE_ENABLED` | Enable the Scanner schedule | `false` |
| `SCANNER_SCHEDULE_TIME` | Scanner pre-open execution time | `08:40` |
| `SCANNER_SCHEDULE_RUN_IMMEDIATELY` | Run Scanner once on process startup | `false` |
| `SCANNER_NOTIFICATION_ENABLED` | Send notification after scheduled Scanner runs | `true` |
| `SCANNER_LOCAL_UNIVERSE_PATH` | Local A-share universe cache path for Scanner | `./data/scanner_cn_universe_cache.csv` |
| `LOG_DIR` | Log directory | `./logs` |

> Behavior notes:
> - When `TICKFLOW_API_KEY` is configured, CN market review first tries TickFlow for main indices. Market breadth also tries TickFlow only when the current TickFlow plan supports universe queries.
> - TickFlow behavior is capability-based rather than just key-based: limited plans can still enhance main CN indices, while plans with `CN_Equity_A` universe query support also enhance market breadth.
> - The official quickstart documents `quotes.get(universes=["CN_Equity_A"])`, but online smoke tests confirmed two additional real-world constraints: universe access depends on plan permissions, and `quotes.get(symbols=[...])` has a per-request symbol limit.
> - TickFlow currently returns `change_pct` / `amplitude` as ratio values; this integration normalizes them to the project's percent convention so they match AkShare / Tushare / efinance semantics.
> - Per-stock analysis, realtime quote priority, and sector rankings fallback remain unchanged.

---

## Docker Deployment

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 2. Configure environment variables
cp .env.example .env
vim .env  # Fill in API Keys and configuration

# 3. Start container
docker-compose -f ./docker/docker-compose.yml up -d server     # Web service mode (recommended, provides API & WebUI)
docker-compose -f ./docker/docker-compose.yml up -d analyzer   # Scheduled task mode
docker-compose -f ./docker/docker-compose.yml up -d            # Start both modes

# 4. Access WebUI
# http://localhost:8000

# 5. View logs
docker-compose -f ./docker/docker-compose.yml logs -f server
```

### Run Mode Description

| Command | Description | Port |
|------|------|------|
| `docker-compose -f ./docker/docker-compose.yml up -d server` | Web service mode, provides API & WebUI | 8000 |
| `docker-compose -f ./docker/docker-compose.yml up -d analyzer` | Scheduled task mode, daily auto execution | - |
| `docker-compose -f ./docker/docker-compose.yml up -d` | Start both modes simultaneously | 8000 |

### Docker Compose Configuration

`docker-compose.yml` uses YAML anchors to reuse configuration:

```yaml
version: '3.8'

x-common: &common
  build: .
  restart: unless-stopped
  env_file:
    - .env
  environment:
    - TZ=Asia/Shanghai
  volumes:
    - ./data:/app/data
    - ./logs:/app/logs
    - ./reports:/app/reports
    - ./.env:/app/.env

services:
  # Scheduled task mode
  analyzer:
    <<: *common
    container_name: stock-analyzer

  # FastAPI mode
  server:
    <<: *common
    container_name: stock-server
    command: ["python", "main.py", "--serve-only", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "8000:8000"
```

### Common Commands

```bash
# View running status
docker-compose -f ./docker/docker-compose.yml ps

# View logs
docker-compose -f ./docker/docker-compose.yml logs -f server

# Stop services
docker-compose -f ./docker/docker-compose.yml down

# Rebuild image (after code update)
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d server
```

### Manual Image Build

```bash
docker build -t stock-analysis .
docker run -d --env-file .env -p 8000:8000 -v ./data:/app/data stock-analysis python main.py --serve-only --host 0.0.0.0 --port 8000
```

---

## Local Deployment

### Install Dependencies

```bash
# Python 3.10+ recommended
pip install -r requirements.txt

# Or use conda
conda create -n stock python=3.10
conda activate stock
pip install -r requirements.txt
```

### Command Line Arguments

```bash
python main.py                        # Full analysis (stocks + market review)
python main.py --market-review        # Market review only
python main.py --no-market-review     # Stock analysis only
python main.py --stocks 600519,300750 # Specify stocks
python main.py --dry-run              # Fetch data only, no AI analysis
python main.py --no-notify            # Don't send notifications
python main.py --schedule             # Scheduled task mode
python main.py --debug                # Debug mode (verbose logging)
python main.py --workers 5            # Specify concurrency
```

---

## Scheduled Task Configuration

### GitHub Actions Schedule

Edit `.github/workflows/daily_analysis.yml`:

```yaml
schedule:
  # UTC time, Beijing time = UTC + 8
  - cron: '0 10 * * 1-5'   # Monday to Friday 18:00 (Beijing Time)
```

Common time reference:

| Beijing Time | UTC cron expression |
|---------|----------------|
| 09:30 | `'30 1 * * 1-5'` |
| 12:00 | `'0 4 * * 1-5'` |
| 15:00 | `'0 7 * * 1-5'` |
| 18:00 | `'0 10 * * 1-5'` |
| 21:00 | `'0 13 * * 1-5'` |

### Local Scheduled Tasks

```bash
# Start scheduled mode (default 18:00 execution)
python main.py --schedule

# Or use crontab
crontab -e
# Add: 0 18 * * 1-5 cd /path/to/project && python main.py
```

### Scanner Pre-open Schedule

Market Scanner uses a separate schedule instead of sharing semantics with the normal analysis workflow:

```bash
# Run one manual A-share scanner job
python main.py --scanner

# Start the Scanner schedule
python main.py --scanner-schedule

# Run both the analysis schedule and the Scanner schedule
python main.py --schedule --scanner-schedule
```

The intended first setup is a pre-open run such as `08:40`. Each run produces a persistent daily watchlist that can later be reviewed from `/scanner`, `GET /api/v1/scanner/watchlists/today`, and `GET /api/v1/scanner/watchlists/recent`.

### Scanner Schedule Environment Variables

| Variable | Description | Default | Example |
|--------|------|:-------:|:-----:|
| `SCANNER_SCHEDULE_ENABLED` | Enable the Scanner schedule | `false` | `true` |
| `SCANNER_SCHEDULE_TIME` | Scanner daily pre-open time (HH:MM) | `08:40` | `08:40` |
| `SCANNER_SCHEDULE_RUN_IMMEDIATELY` | Run one Scanner job on startup | `false` | `true` |
| `SCANNER_NOTIFICATION_ENABLED` | Send a notification after scheduled Scanner runs | `true` | `true` |
| `SCANNER_LOCAL_UNIVERSE_PATH` | Local A-share universe cache path for Scanner | `./data/scanner_cn_universe_cache.csv` | `./data/scanner_cn_universe_cache.csv` |

### Scanner Daily Watchlists And Notifications

With P9, Scanner output is treated as a persistent daily watchlist instead of an ephemeral table dump.

- `today watchlist`: the preferred run for the current watchlist date
- `recent watchlists`: lightweight day-level review of recent shortlists
- `trigger_mode`: distinguishes `manual` from `scheduled`
- `notification`: stores delivery success/failure
- `failure`: stores a basic failure reason when a run fails

The notification layer reuses the existing notification infrastructure. If the repo already has WeChat / Feishu / Telegram / Email / Slack or another supported channel configured, a scheduled Scanner run can push a compact pre-open shortlist automatically.

If no candidate passes the threshold, the run is stored as `empty` instead of silently disappearing. If the run fails, it is stored as `failed` with a persisted failure reason.

---

## Notification Channel Configuration

### WeChat Work

1. Add "Group Bot" in WeChat Work group chat
2. Copy Webhook URL
3. Set `WECHAT_WEBHOOK_URL`

### Feishu

1. Add "Custom Bot" in Feishu group chat
2. Copy Webhook URL
3. Set `FEISHU_WEBHOOK_URL`

### Telegram

1. Talk to @BotFather to create a Bot
2. Get Bot Token
3. Get Chat ID (via @userinfobot)
4. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
5. (Optional) To send to Topic, set `TELEGRAM_MESSAGE_THREAD_ID` (get from Topic link)

### Email

1. Enable SMTP service for your email
2. Get authorization code (not login password)
3. Set `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVERS`

Supported email providers:
- QQ Mail: smtp.qq.com:465
- 163 Mail: smtp.163.com:465
- Gmail: smtp.gmail.com:587

### Custom Webhook

Supports any POST JSON Webhook, including:
- DingTalk Bot
- Discord Webhook
- Slack Webhook
- Bark (iOS push)
- Self-hosted services

Set `CUSTOM_WEBHOOK_URLS`, separate multiple with commas.

### Discord

Discord supports two push methods:

**Method 1: Webhook (Recommended, Simple)**

1. Create Webhook in Discord channel settings
2. Copy Webhook URL
3. Configure environment variable:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
```

**Method 2: Bot API (Requires more permissions)**

1. Create application in [Discord Developer Portal](https://discord.com/developers/applications)
2. Create Bot and get Token
3. Invite Bot to server
4. Get Channel ID (right-click channel in developer mode)
5. Configure environment variables:

```bash
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_MAIN_CHANNEL_ID=your_channel_id
```

### Slack

Slack supports two push methods. When both are configured, Bot API takes priority to ensure text and images land in the same channel:

**Method 1: Bot API (Recommended, supports image upload)**

1. Create a Slack App: https://api.slack.com/apps → Create New App
2. Add Bot Token Scopes: `chat:write`, `files:write`
3. Install to workspace and get Bot Token (xoxb-...)
4. Get Channel ID: channel details → copy channel ID at the bottom
5. Configure environment variables:

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C01234567
```

**Method 2: Incoming Webhook (Simple setup, text only)**

1. Create an Incoming Webhook in Slack App management page
2. Copy the Webhook URL
3. Configure environment variable:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx
```

### Pushover (iOS/Android Push)

[Pushover](https://pushover.net/) is a cross-platform push service supporting iOS and Android.

1. Register Pushover account and download App
2. Get User Key from [Pushover Dashboard](https://pushover.net/)
3. Create Application to get API Token
4. Configure environment variables:

```bash
PUSHOVER_USER_KEY=your_user_key
PUSHOVER_API_TOKEN=your_api_token
```

Features:
- Supports iOS/Android
- Supports notification priority and sound settings
- Free quota sufficient for personal use (10,000 messages/month)
- Messages retained for 7 days

---

## Data Source Configuration

System defaults to AkShare (free), also supports other data sources:

### AkShare (Default)
- Free, no configuration needed
- Data source: Eastmoney scraper

### Tushare Pro
- Requires registration to get Token
- More stable, more comprehensive data
- Set `TUSHARE_TOKEN`

### Baostock
- Free, no configuration needed
- Used as backup data source

### YFinance
- Free, no configuration needed
- Supports US/HK stock data
- US stock historical and real-time data both use YFinance exclusively to avoid technical indicator errors from akshare's US stock adjustment issues

---

## Advanced Features

### Hong Kong Stock Support

Use `hk` prefix for HK stock codes:

```bash
STOCK_LIST=600519,hk00700,hk01810
```

### Multi-Model Switching

Configure multiple models, system auto-switches:

```bash
# Gemini (primary)
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3-flash-preview

# OpenAI compatible (backup)
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
# Thinking mode: deepseek-reasoner, deepseek-r1, qwq auto-detected; deepseek-chat enabled by model name
```

### LiteLLM Direct Integration (Multi-Model + Multi-Key Load Balancing)

See [LLM Config Guide](LLM_CONFIG_GUIDE_EN.md). This project uses [LiteLLM](https://github.com/BerriAI/litellm) to unify all LLM calls; no separate Proxy service required.

**Two-layer mechanism**: Same-model multi-key rotation (Router) and cross-model fallback are independent.

**Multi-key + cross-model fallback example**:

```env
# Primary: 3 Gemini keys rotate; Router switches on 429
GEMINI_API_KEYS=key1,key2,key3
LITELLM_MODEL=gemini/gemini-3-flash-preview

# Cross-model fallback: when all primary keys fail, try Claude → GPT
# Requires ANTHROPIC_API_KEY, OPENAI_API_KEY
LITELLM_FALLBACK_MODELS=anthropic/claude-3-5-sonnet-20241022,openai/gpt-4o-mini
```

> ⚠️ `LITELLM_MODEL` must include provider prefix (e.g. `gemini/`, `anthropic/`, `openai/`). Legacy `GEMINI_MODEL` (no prefix) is only used when `LITELLM_MODEL` is not set.

**Vision model (image stock code extraction)**: See [LLM Config Guide - Vision](LLM_CONFIG_GUIDE_EN.md#41-vision-model-image-stock-code-extraction).

### Debug Mode

```bash
python main.py --debug
```

Log file locations:
- Regular logs: `logs/stock_analysis_YYYYMMDD.log`
- Debug logs: `logs/stock_analysis_debug_YYYYMMDD.log`

---

## Backtesting

The backtest domain now has two explicit modules:

1. **Historical Analysis Evaluation**
   Validates historical AI analysis records from `AnalysisHistory` against later market moves.
2. **Deterministic Rule Strategy Backtest**
   Parses natural-language rules into structured entry / exit logic, then runs an auditable rule-based trading replay with explicit execution assumptions.

### How It Works

#### A. Historical Analysis Evaluation

1. Selects `AnalysisHistory` records past the maturity window (default 14 calendar days)
2. Fetches daily bar data after the analysis date (forward trading bars)
3. Infers expected direction from the operation advice and compares it against actual movement
4. Evaluates stop-loss/take-profit hit conditions and simulated returns
5. Aggregates overall and per-stock performance metrics

#### B. Deterministic Rule Strategy Backtest

1. Parses natural-language strategy text into normalized entry / exit rules
2. Loads market history, preferring local US parquet files when applicable
3. Runs the strategy with explicit signal timing, fill timing, price basis, position sizing, fees, and slippage assumptions
4. Produces trade audits, equity curve, buy-and-hold benchmark, and excess return
5. Submits asynchronously by default and exposes run-id based status polling

The Web result view now follows one deterministic rendering pipeline as well:

- It first normalizes the stored deterministic result into one `normalized rows / metrics / tradeEvents / benchmarkMeta / viewerMeta` payload
- KPI cards, the linked chart workspace, the audit table, and the trade/event table all read from that same normalized payload instead of rebuilding their own timelines
- The current run result and any history-opened run reuse the same chart workspace, with one shared visible window and hover state across return, daily PnL, position, and the bottom brush
- The Web product flow is now formally split into two pages: `/backtest` handles deterministic backtest configuration and launch only, while `/backtest/results/:runId` is the full-width result analysis page
- Launching from the configuration page navigates straight into the result page flow, and deterministic history items reuse that same result route instead of replaying the full analysis inline on `/backtest`
- The result page first screen is now chart-centered: the default view keeps only the top summary, KPI cards, and the unified chart workspace, while day-level inspection moves into a hover-linked floating detail card and the audit/trade/parameter/history content moves into tabs and collapsible sections
- The first screen has also been compacted into a dashboard-style hero: the header is now an even thinner top bar, the KPI area is a lower-height key-metric row, and the linked multi-panel chart workspace uses shorter panel heights again (about `220 / 72 / 56 / 40px` in dense mode) so the overview stays coherent without losing readability
- The hover detail is now positioned from live hover geometry instead of staying pinned in a corner, with the tooltip defaulting to the lower-right of the hover point and flipping only when it nears an edge, so it follows the cursor/crosshair inside the chart workspace like a real inspection overlay
- The result page now uses an explicit shared density system (`comfortable / compact / dense`) to drive the header, KPI row, panel heights, legend, brush, tooltip, and spacing together, instead of letting each area shrink independently
- The hover tooltip also now uses a tooltip-specific label/value layout: primary metrics stay in a stable two-column grid, longer text moves into wrapping detail blocks, and the card enforces a max width / max height with internal scrolling instead of overflowing outward
- Starting in P6, the `History` tab on the result page adds a lightweight compare workflow: the current run stays pinned as the baseline, and users can select up to three completed runs for side-by-side comparison across return, excess return, drawdown, win rate, ending equity, and strategy setup, with fairness warnings when date ranges, fee/slippage assumptions, or benchmark settings differ
- P6 also makes the chart workspace more decision-oriented: the main panel still keeps strategy vs benchmark vs buy-and-hold, the second panel now prioritizes drawdown, and the third panel can switch between `relative vs benchmark / daily PnL / position behavior` so users can judge faster whether the strategy outperformed, what it cost, and whether trading activity became too noisy
- The `Parameters & Assumptions` tab now includes a controlled `Scenario Lab` for lightweight strategy iteration on supported rule strategies, covering deterministic first-step variants such as MA windows, MACD/RSI variants, benchmark mode, fee/slippage stress, and lookback windows, then summarizing them against the current run in a compact comparison view instead of acting like a full optimizer
- The `Overview` tab now generates an exportable decision summary (Markdown / HTML) that leads with a human-readable report and keeps CSV / JSON execution-trace export as the deeper layer; the result flow also auto-saves recent drafts and supports named presets so users can quickly reuse prior configurations from the launch page without rebuilding the whole setup

Recommended P6 manual checks:

1. Finish one rule backtest, open the `History` tab, and select 1-3 completed runs to confirm the side-by-side comparison, normalized progress chart, and fairness warnings all appear as expected.
2. Review the first-screen chart workspace and switch the third panel mode to confirm you can quickly read outperformance vs benchmark/buy-and-hold, drawdown severity, and trading activity.
3. Open `Parameters & Assumptions -> Scenario Lab`, launch one scenario group, and confirm the variants reuse the existing async run, polling, and result-detail flow before appearing in the compact baseline-vs-variant comparison area.
4. Export the Markdown / HTML decision summary from the `Overview` tab, and also confirm CSV / JSON execution-trace export still works with the decision summary positioned ahead of the deep trace.
5. Save a named preset from the result page, return to `/backtest`, and confirm the `Quick Reuse` section shows the recent draft / preset and restores code, strategy text, date range, lookback, fee/slippage, and benchmark settings.

### Operation Advice Mapping

| Operation Advice | Position | Expected Direction | Win Condition |
|-----------------|----------|-------------------|---------------|
| Buy / Add / Strong Buy | long | up | Return >= neutral band |
| Sell / Reduce / Strong Sell | cash | down | Decline >= neutral band |
| Hold | long | not_down | No significant decline |
| Wait / Observe | cash | flat | Price within neutral band |

### Configuration

Set the following variables in `.env` (all optional, have defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKTEST_ENABLED` | `true` | Whether to auto-run backtest after daily analysis |
| `BACKTEST_EVAL_WINDOW_DAYS` | `10` | Historical analysis evaluation window (trading bars) |
| `BACKTEST_MIN_AGE_DAYS` | `14` | Historical sample maturity window (calendar days; `0` disables the maturity gate) |
| `BACKTEST_ENGINE_VERSION` | `v1` | Engine version, used to distinguish results when logic is updated |
| `BACKTEST_NEUTRAL_BAND_PCT` | `2.0` | Neutral band threshold (%), ±2% treated as range-bound |
| `LOCAL_US_PARQUET_DIR` | `/root/us_test/data/normalized/us` | Preferred local US parquet root reused by stock history, historical evaluation, and rule backtests; falls back to `US_STOCK_PARQUET_DIR` for legacy compatibility |

### Auto-run

Backtesting triggers automatically after the daily analysis flow completes (non-blocking; failures do not affect notifications). It can also be triggered manually via API.

### Evaluation Metrics

| Metric | Description |
|--------|-------------|
| `direction_accuracy_pct` | Direction prediction accuracy (expected direction matches actual) |
| `win_rate_pct` | Win rate (wins / (wins + losses), excludes neutral) |
| `avg_stock_return_pct` | Average stock return percentage |
| `avg_simulated_return_pct` | Average simulated execution return (including SL/TP exits) |
| `stop_loss_trigger_rate` | Stop-loss trigger rate (only counts records with SL configured) |
| `take_profit_trigger_rate` | Take-profit trigger rate (only counts records with TP configured) |

### Rule Backtest Execution Assumptions

Deterministic rule backtests return the following assumptions explicitly so the semantics are auditable:

- `timeframe`: current rule timeframe (default `daily`)
- `price_basis`: signal calculation price basis (currently `close`)
- `signal_evaluation_timing`: signals are evaluated at bar close
- `entry_fill_timing`: entries fill on the next bar open
- `exit_fill_timing`: exits fill on the next bar open; the last bar may force-close at close
- `position_sizing`: 100% capital when long, otherwise cash
- `fee_bps_per_side` / `slippage_bps_per_side`: per-side fee and slippage
- `benchmark_method`: benchmarked against buy-and-hold over the same window

---

## FastAPI API Service

FastAPI provides RESTful API service for configuration management and triggering analysis.

### Startup Methods

| Command | Description |
|------|------|
| `python main.py --serve` | Start API service + run full analysis once |
| `python main.py --serve-only` | Start API service only, manually trigger analysis |

### Features

- **Configuration Management** - View/modify watchlist
- **Quick Analysis** - Trigger analysis via API
- **Real-time Progress** - Analysis task status updates in real-time, supports parallel tasks
- **Backtest Validation** - Historical analysis evaluation plus deterministic rule strategy backtests, including run status, trade auditability, and buy-and-hold benchmarking
- **API Documentation** - Visit `/docs` for Swagger UI

### API Endpoints

| Endpoint | Method | Description |
|------|------|------|
| `/api/v1/analysis/analyze` | POST | Trigger stock analysis |
| `/api/v1/analysis/tasks` | GET | Query task list |
| `/api/v1/analysis/status/{task_id}` | GET | Query task status |
| `/api/v1/history` | GET | Query analysis history |
| `/api/v1/backtest/run` | POST | Trigger historical analysis evaluation |
| `/api/v1/backtest/prepare-samples` | POST | Prepare historical analysis evaluation samples for a symbol |
| `/api/v1/backtest/sample-status` | GET | Query prepared sample coverage |
| `/api/v1/backtest/results` | GET | Query historical analysis evaluation results (paginated) |
| `/api/v1/backtest/samples/clear` | POST | Clear prepared historical analysis evaluation samples |
| `/api/v1/backtest/results/clear` | POST | Clear historical analysis evaluation results |
| `/api/v1/backtest/performance` | GET | Get overall historical analysis evaluation performance |
| `/api/v1/backtest/performance/{code}` | GET | Get per-stock historical analysis evaluation performance |
| `/api/v1/backtest/rule/parse` | POST | Parse rule strategy text |
| `/api/v1/backtest/rule/run` | POST | Submit or synchronously run deterministic rule backtests |
| `/api/v1/backtest/rule/runs` | GET | Query rule backtest history |
| `/api/v1/backtest/rule/runs/{run_id}` | GET | Query a rule backtest detail record |
| `/api/v1/backtest/rule/runs/{run_id}/status` | GET | Query lightweight rule run status |
| `/api/v1/backtest/rule/runs/{run_id}/cancel` | POST | Best-effort cancel a rule run |
| `/api/health` | GET | Health check |
| `/docs` | GET | API Swagger documentation |

> Note: `POST /api/v1/analysis/analyze` supports only one stock when `async_mode=false`; batch `stock_codes` requires `async_mode=true`. The async `202` response returns a single `task_id` for one stock, or an `accepted` / `duplicates` summary for batch requests.
>
> See [docs/backtest-system_EN.md](./backtest-system_EN.md) for repaired backtest ownership, local parquet priority, and smoke-script usage.

**Usage examples**:
```bash
# Health check
curl http://127.0.0.1:8000/api/health

# Trigger analysis (A-shares)
curl -X POST http://127.0.0.1:8000/api/v1/analysis/analyze \
  -H 'Content-Type: application/json' \
  -d '{"stock_code": "600519"}'

# Query task status
curl http://127.0.0.1:8000/api/v1/analysis/status/<task_id>

# Trigger historical analysis evaluation (all stocks)
curl -X POST http://127.0.0.1:8000/api/v1/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"force": false}'

# Trigger historical analysis evaluation (specific stock)
curl -X POST http://127.0.0.1:8000/api/v1/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"code": "600519", "force": false, "eval_window_days": 10, "min_age_days": 14}'

# Prepare historical analysis evaluation samples
curl -X POST http://127.0.0.1:8000/api/v1/backtest/prepare-samples \
  -H 'Content-Type: application/json' \
  -d '{"code": "AAPL", "sample_count": 60, "eval_window_days": 10, "min_age_days": 14}'

# Query overall historical analysis evaluation performance
curl http://127.0.0.1:8000/api/v1/backtest/performance

# Query per-stock historical analysis evaluation performance
curl http://127.0.0.1:8000/api/v1/backtest/performance/600519

# Paginated historical analysis evaluation results
curl "http://127.0.0.1:8000/api/v1/backtest/results?page=1&limit=20"

# Submit asynchronous rule backtest
curl -X POST http://127.0.0.1:8000/api/v1/backtest/rule/run \
  -H 'Content-Type: application/json' \
  -d '{"code":"AAPL","strategy_text":"Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.","lookback_bars":252,"fee_bps":0,"slippage_bps":0,"confirmed":true,"wait_for_completion":false}'

# Poll rule backtest status
curl http://127.0.0.1:8000/api/v1/backtest/rule/runs/123/status

# Query rule backtest detail
curl http://127.0.0.1:8000/api/v1/backtest/rule/runs/123

# Cancel an unfinished rule backtest
curl -X POST http://127.0.0.1:8000/api/v1/backtest/rule/runs/123/cancel
```

Backtest smoke suites:

```bash
python3 test_backtest_basic.py
python3 test_backtest_rule.py
python3 test_backtest_run.py --mode both
```

### Custom Configuration

Modify default port or allow LAN access:

```bash
python main.py --serve-only --host 0.0.0.0 --port 8888
```

### Supported Stock Code Formats

| Type | Format | Examples |
|------|------|------|
| A-shares | 6-digit number | `600519`, `000001`, `300750` |
| BSE (Beijing) | 8/4/92 prefix, 6-digit | `920748`, `838163`, `430047` |
| HK stocks | hk + 5-digit number | `hk00700`, `hk09988` |

### Notes

- Browser access: `http://127.0.0.1:8000` (or your configured port)
- After analysis completion, notifications are automatically pushed to configured channels
- This feature is automatically disabled in GitHub Actions environment

---

## FAQ

### Q: Push messages getting truncated?
A: WeChat Work/Feishu have message length limits, system already auto-segments messages. For complete content, configure Feishu Cloud Document feature.

### Q: Data fetch failed?
A: AkShare uses scraping mechanism, may be temporarily rate-limited. System has retry mechanism configured, usually just wait a few minutes and retry.

### Q: How to add watchlist stocks?
A: Modify `STOCK_LIST` environment variable, separate multiple codes with commas.

### Q: GitHub Actions not executing?
A: Check if Actions is enabled, and if cron expression is correct (note it's UTC time).

---

## Web Product Experience Notes

- The Web app now runs on one shared product shell and design system: login, boot loading, sidebar navigation, home, portfolio, backtest, and admin logs use the same typography, spacing, surface layering, and state-feedback language.
- The backtest product flow now treats deterministic configuration and deterministic result analysis as two separate pages: `/backtest` stays configuration-first, while `/backtest/results/:runId` owns the full-width chart workspace and audit flow.
- On mobile, navigation now consistently uses the shared drawer shell, and loading states favor structured skeleton/status surfaces instead of unrelated spinner-only treatments.

## Portfolio Web Notes

### Manual FX refresh on `/portfolio`

- The FX status card on the Web `/portfolio` page includes a manual refresh action.
- The button calls the existing `POST /api/v1/portfolio/fx/refresh` endpoint and reloads snapshot/risk data only.
- If upstream FX fetch fails, the page may still remain stale after refresh and will explain the fallback result inline.
- When `PORTFOLIO_FX_UPDATE_ENABLED=false`, the refresh API returns an explicit disabled status and the page shows that online FX refresh is disabled instead of implying that no refreshable pairs exist.

---

For more questions, please [submit an Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues)
