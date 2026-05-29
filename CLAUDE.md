# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run market review (main entry point)
python main.py

# Common flags
python main.py --force-run          # ignore trading day check
python main.py --no-notify          # run but skip Telegram send
python main.py --debug              # verbose logging
python main.py --no-market-review   # skip market review entirely

# Tests
pytest tests/ -v
pytest tests/test_config_validate_structured.py  # single file
pytest tests/ -k "test_name"                     # single test by name

# Install dependencies
pip install -r requirements.txt
```

## Architecture

This is a **daily automated US market review system** that fetches market data, aggregates news, runs Gemini AI analysis, and delivers a structured report to Telegram.

### Entry Point and Flow

`main.py` → `src/core/market_review.py:run_market_review()` is the critical path:

1. Load config singleton (`src/config.py:get_config()`)
2. Check trading calendar (`src/core/trading_calendar.py`) — skips non-US trading days unless `--force-run`
3. `MarketAnalyzer` (`src/market_analyzer.py`) fetches US index data (SPY, QQQ, DJI, VIX, Gold) via `data_provider/`
4. `SearchService` (`src/search_service.py`) aggregates news from Tavily/SerpAPI/Brave/Finnhub with automatic key rotation
5. `GeminiAnalyzer` (`src/analyzer.py`) sends data to Gemini via LiteLLM and parses the structured JSON response
6. Portfolio P&L loaded from Google Sheets (`src/portfolio/google_sheets_reader.py`) and appended to report
7. `NotificationService` (`src/notification.py`) + `TelegramSender` (`src/notification_sender/telegram_sender.py`) delivers HTML-formatted message

### Key Modules

| Module | Role |
|--------|------|
| `src/config.py` | Singleton dataclass config; reads `.env`; validates required keys |
| `src/analyzer.py` | LiteLLM wrapper for Gemini; handles fallback model, JSON repair, token counting |
| `src/market_analyzer.py` | Builds the 4-section market review (indices, events, sector rotation, watchlist) |
| `src/search_service.py` | Multi-provider news search; auto-rotates API keys; deduplicates results |
| `src/stock_analyzer.py` | Technical analysis (MA/MACD/RSI/volume); produces `TrendAnalysisResult` |
| `data_provider/base.py` | Strategy pattern fetcher manager; yfinance is the primary provider |
| `src/storage.py` | SQLAlchemy ORM over SQLite (`data/analysis.db`) for OHLCV and analysis cache |
| `src/core/signal_filter.py` | Consecutive-day filter: same buy signal required 2 days in a row to fire |
| `src/core/budget_tracker.py` | Monthly deployment tracker; 45% first buy, 30% second buy rule |
| `src/core/earnings_evaluator.py` | FMP earnings data → Gemini evaluation; gated by `EARNINGS_EVAL_ENABLED` |
| `src/bot/telegram_listener.py` | Hourly-polled Telegram bot for on-demand analysis commands |

### Scheduling

All production runs are via GitHub Actions, not a local scheduler:

- `daily_analysis.yml` — cron 22:00 UTC (08:00 MYT), runs after US market close
- `bot_listener.yml` — cron every hour for Telegram bot polling
- `daily_news.yml` — daily news aggregation

Secrets (API keys, tokens) live in GitHub Actions secrets, not committed files.

### Configuration

Config is loaded once at startup into a frozen singleton. All modules call `get_config()` to access it. Multi-value env vars (e.g. `TAVILY_API_KEYS`) accept comma-separated values for automatic key rotation.

Runtime state files (created automatically in `data/`):
- `analysis.db` — SQLite OHLCV and analysis cache
- `signal_history.json` — tracks consecutive-day buy signals
- `bot_state.json` — tracks processed Telegram message IDs
- `budget.json` — monthly cash deployment tracker

### LLM Integration

`GeminiAnalyzer` uses LiteLLM for provider-agnostic calls. The primary model is `LITELLM_MODEL` (default: `gemini/gemini-2.5-flash`), with automatic fallback to `GEMINI_MODEL_FALLBACK`. Responses are expected as structured JSON; `json_repair` handles malformed outputs. To swap providers, change `LITELLM_MODEL` in `.env` (e.g., `openai/gpt-4o`, `anthropic/claude-3-5-sonnet`).

### Telegram Output

Messages are formatted in **HTML** (not Markdown) because it renders more reliably in Telegram mobile clients. All `TelegramSender` output uses `<b>`, `<i>`, `<code>` tags. The market review is written primarily in **Chinese**.
