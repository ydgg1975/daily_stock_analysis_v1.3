# English Local Handoff

This document captures the current English trial setup for `daily_stock_analysis`.
It is written for a future operator who may need to continue work from another
machine.

## Current GitHub State

The original upstream repository is:

<https://github.com/ZhuLinsen/daily_stock_analysis>

Direct push access to that repository was denied for the current GitHub account,
so the English trial work is pushed to this fork branch instead:

<https://github.com/N9ALV/daily_stock_analysis/tree/codex/english-ui-styling>

The local commit that introduced the English trial, OpenRouter defaults, UI
colour, and button-radius changes is:

```text
f7fb3386 localise web UI and refine test styling
```

Use this command to clone the branch on another machine:

```powershell
git clone --branch codex/english-ui-styling https://github.com/N9ALV/daily_stock_analysis.git
cd daily_stock_analysis
```

If you want to compare against the upstream project later:

```powershell
git remote add upstream https://github.com/ZhuLinsen/daily_stock_analysis.git
git fetch upstream
```

## What Was Changed For The Trial

- Web UI text was localised to English for the basic user flow.
- Remaining Chinese labels in common buttons, toggles, empty states, settings
  panels, and report controls were translated where they affected the local
  trial path.
- The default local AI provider path was configured for OpenRouter-compatible
  usage with `deepseek-v4-flash`.
- The frontend build was generated so visiting `http://127.0.0.1:8000/` opens
  the app rather than FastAPI documentation.
- The light blue / teal accent colour was replaced with `#4054b2`.
- Button corner radii were capped at `11px`.
- A local English smoke script was added at `scripts/local_english_smoke.py`.

This is still an evaluation fork, not a final product fork. China-market data
sources can still return Chinese index, sector, and company names inside market
reports. For a clean English test, use US tickers such as `AAPL`, `MSFT`, or
`NVDA`.

## Local Secret Setup

Do not commit API keys. Store them in `.env` on each machine.

For OpenRouter, create or edit `.env` in the repository root and set the
OpenAI-compatible values expected by the app. Example shape:

```dotenv
OPENAI_API_KEY=your-openrouter-key
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-v4-flash
REPORT_LANGUAGE=en
```

The exact environment variable names may be expanded by future work; check
`.env.example` and the settings UI before publishing.

## Run Locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe main.py --serve-only
```

Then open:

<http://127.0.0.1:8000/>

If the browser shows `Frontend Not Built`, build the web app:

```powershell
cd apps\dsa-web
npm install
npm run build
cd ..\..
.\.venv\Scripts\python.exe main.py --serve-only
```

## Beginner Test Script

Use this manual test before deciding whether to invest in a permanent fork:

1. Open <http://127.0.0.1:8000/>.
2. On the Home page, enter `AAPL`.
3. Click `Analyse`.
4. Wait for the task to finish.
5. Click the new `AAPL` item in the history list.
6. Confirm the report and controls are English.
7. Open `Ask AI`.
8. Ask: `Summarise AAPL in plain English.`
9. Confirm the response is English and uses the configured OpenRouter model.

Expected visual checks:

- Primary accent colour should be `#4054b2`.
- Buttons should look moderately rounded, with a maximum radius of `11px`.
- The app should appear at `/`, not only at `/docs`.

## Automated Local Checks

Frontend build:

```powershell
cd apps\dsa-web
npm run build -- --logLevel silent
cd ..\..
```

English smoke test:

```powershell
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe scripts\local_english_smoke.py
```

Health check while the server is running:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

## Where Previous Runs Are Stored

The app stores analysis history in SQLite:

```text
data/stock_analysis.db
```

Generated Markdown reports are written under:

```text
reports/
```

Both paths are ignored by Git because they are local runtime artefacts and may
contain sensitive or bulky data. Preserve them in a separate backup bundle when
moving machines.

## Backup And Restore Checklist

For a portable handoff, preserve:

- The Git branch or a repository archive.
- `.env`, kept outside Git.
- `data/stock_analysis.db` plus `stock_analysis.db-wal` and
  `stock_analysis.db-shm` if present.
- The `reports/` folder.
- Any screenshots or notes under `reports/ui-checks/`.
- This document.

Restore on another Windows machine:

1. Clone the GitHub branch.
2. Copy `.env` into the repository root.
3. Copy `data/` and `reports/` into the repository root if old history matters.
4. Create a Python virtual environment and install `requirements.txt` if the
   bundled `.venv` was not copied.
5. Build `apps/dsa-web`.
6. Run `.\.venv\Scripts\python.exe main.py --serve-only`.

## Publishing Notes

Before treating this as a publishable fork:

- Rebase or merge current upstream carefully. The local branch was behind
  upstream during this handoff.
- Decide whether to keep China-market features or create a US/English-only fork.
- Replace local `.env` secrets with repository or deployment secrets.
- Run backend tests and frontend tests, not just the smoke checks above.
- Review all provider names and model defaults for the target deployment.
