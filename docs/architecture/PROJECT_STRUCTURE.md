# Project Structure (Cleaned)

## Runtime Core
- `bot.py` - main entrypoint and composition root
- `chatbot/` - Telegram runtime, providers, copilot, analytics
- `app/` - modular handlers, domain models, repositories, services

## Operations
- `start_bot.sh`, `stop_bot.sh`, `status_bot.sh`, `supervise_bot.sh`
- `run_tests.sh`, `Makefile`

## Documentation
- `README.md`, `DEPLOY.md`
- `docs/architecture/` - architecture docs
- `docs/guides/` - active implementation and ops guides
- `docs/archive/` - historical status and completion notes

## Utility Scripts
- `scripts/integration/` - integration checks and helper scripts
- `scripts/dev/` - local dev helper scripts

## Data / Runtime Artifacts
- `portfolio.db`, `market_cache.db`, `portfolio_state.json`, `bot.log`

## Notes
- Current architecture is hybrid (`chatbot/*` + `app/*`) in one process.
- Legacy backup files and stale root-level status docs were removed/moved for readability.
