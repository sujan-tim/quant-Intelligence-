# Quant Intelligence Platform

A local stock research app with a plain-language dashboard. It can load fictional demo prices or real historical daily prices from Alpha Vantage, calculate indicators, show a transparent forecast baseline, test one historical strategy, and simulate paper orders. **It does not place real brokerage orders or provide reliable price predictions.**

## Start in two steps

1. Start Docker Desktop.
2. In a terminal, run:

```sh
cd /Users/sujantimilsina/Desktop/quant-intelligence-platform
docker compose up --build
```

Open **http://localhost:8000/** for the dashboard. The services bind to your computer only. The API testing page remains at **http://localhost:8000/docs**.

On the dashboard, choose **Load demo data** to explore without an account. Demo symbols are fictional (`DEMOA`, `DEMOB`, `DEMOC`) and their synthetic bars end on March 30, 2024. Check the source and date beside every result.

To stop, press Ctrl+C in that terminal, then run `docker compose down`. This preserves the PostgreSQL volume. To restart, run `docker compose up --build` again.

## Import real market history

The optional Alpha Vantage integration uses a **key you obtain yourself**. Copy `.env.example` to `.env` and fill in `QIP_ALPHA_VANTAGE_API_KEY`. Restart Docker Compose, then enter a ticker in the dashboard and import it. The key stays on the server; do not commit `.env`.

```sh
cp .env.example .env
# Edit .env and add your key, then:
docker compose up --build
```

The default Alpha Vantage feed is **historical end-of-day daily bars**, not a live price stream. Check `latest_bar_date` before relying on a result. A premium entitlement is required for delayed or real-time US data; setting `QIP_MARKET_DATA_ENTITLEMENT` alone does not grant one. Free API keys have a request limit. Review [Alpha Vantage documentation](https://www.alphavantage.co/documentation/), [API key limits](https://www.alphavantage.co/support/api-key/), [terms](https://www.alphavantage.co/terms_of_service/), and [real-time data policy](https://www.alphavantage.co/realtime_data_policy/) before using or distributing the data. No external source code or provider data is bundled with this repository.

## What the tools mean

- **Rankings:** A 0–100 score combining four configured checks: RSI ≤ 30, MACD above its signal line, SMA20 above SMA50, and latest volume at least twice the previous 20-bar average. It is a screen, not a buy recommendation. Weights and the volume threshold can be changed in `.env`.
- **Forecast baseline:** Repeats the latest closing price as a simple reference point. The displayed range is based on historical absolute moves; it is not a calibrated probability interval or an AI prediction.
- **Backtest:** Simulates a long-only SMA20/SMA50 strategy on stored daily bars. It forms a signal from prior closes, executes at the next open, and includes configurable fees and slippage. It compares the result with buy-and-hold. It omits dividends, corporate actions, taxes, market impact, and data revisions. Historical results do not establish future returns.
- **Paper trading:** Keeps a local simulated cash balance, holdings, and order history. It fills at the **last stored daily close**, which may be old. It does not contact a broker or move money.

This is a local research prototype. It has no user accounts, scheduled market updates, production-grade controls, broker execution, or AI model. No trading decision should be based on its outputs alone.

## API routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/health` | API health |
| POST | `/v1/ingestions/demo` | Load deterministic fictional bars |
| POST | `/v1/ingestions/market` | Import real Alpha Vantage history; JSON `{ "symbol": "AAPL" }` |
| GET | `/v1/market/quote/{symbol}` | Latest available provider quote, with trading date and entitlement |
| GET | `/v1/assets` | Stored assets and sources |
| GET | `/v1/assets/{symbol}/bars` | Most recent stored daily bars |
| GET | `/v1/assets/{symbol}/signals/latest` | Latest calculated indicator snapshot |
| GET | `/v1/rankings` | Score ordering |
| GET | `/v1/assets/{symbol}/forecast?horizon=5` | Last-close baseline and historical band |
| POST | `/v1/backtests` | SMA strategy simulation; JSON `{ "symbol": "AAPL" }` |
| GET | `/v1/paper/portfolio` | Local simulated account |
| POST | `/v1/paper/orders` | Simulated order; JSON `{ "symbol": "AAPL", "side": "buy", "quantity": 1 }` |

## Local Python setup and tests

Python 3.11 or newer and PostgreSQL are required for local server mode.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# Set QIP_DATABASE_URL in .env for your PostgreSQL server.
alembic upgrade head
uvicorn quant_intelligence.main:app --reload
```

Run the automated checks with:

```sh
ruff check .
pytest -q
```

Tests use SQLite in memory for services and HTTP behavior. Docker Compose exercises the PostgreSQL path and runs migrations on startup. CI runs lint and tests on pushes and pull requests.

## Code structure

`providers/base.py` defines the source interface. `providers/demo.py` generates fictional data; `providers/alpha_vantage.py` fetches real data with a user key. `ingestion.py` stores bars and signal snapshots. `signals.py` and `ranking.py` calculate the screen. `analytics.py` implements the baseline and backtest. `paper.py` maintains the simulated ledger. `api.py` serves the API, while `static/` contains the browser dashboard.
