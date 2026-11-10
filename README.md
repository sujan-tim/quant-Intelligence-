# Quant Intelligence Platform

First backend milestone for a modular market data and signal platform. It ships with **synthetic, fixed-date demo data only**. No live market feed, AI model, trading execution, or backtesting is implemented.

## Included

- FastAPI REST API with typed environment settings and a provider protocol.
- Deterministic demo provider: three fictional assets and 90 daily bars each, dated January–March 2024.
- SQLAlchemy asset, price bar, and signal snapshot models with an Alembic migration for PostgreSQL.
- Atomic, repeatable ingestion. The latest snapshot is recalculated from stored bars.
- RSI(14) using Wilder smoothing, MACD(12,26,9), SMA(20/50), and latest volume divided by the previous 20-day average.
- Configurable weighted ranking. Each condition contributes its weight: RSI ≤ 30, MACD above signal, SMA20 above SMA50, and volume ratio ≥ threshold. Score is 0–100. Missing indicators contribute zero. This is a transparent heuristic, not investment advice.

## Run with Docker

```sh
docker compose up --build
```

Compose starts PostgreSQL, applies the migration, then serves the API at `http://localhost:8000`. Open `/docs` for interactive API documentation. Load demo data with:

```sh
curl -X POST http://localhost:8000/v1/ingestions/demo
curl http://localhost:8000/v1/rankings
```

## Run locally

Use Python 3.11 or newer and a running PostgreSQL database.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn quant_intelligence.main:app --reload
```

Change `QIP_DATABASE_URL` in `.env` for your database. Ranking weights and volume threshold are also configured there. Set `QIP_DEMO_PROVIDER_ENABLED=false` to disable demo ingestion.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/health` | Process health |
| POST | `/v1/ingestions/demo` | Load or refresh synthetic demo bars |
| GET | `/v1/assets` | List stored assets and data sources |
| GET | `/v1/assets/{symbol}/bars?limit=100` | Most recent bars first |
| GET | `/v1/assets/{symbol}/signals/latest` | Latest indicator values and ranking flags |
| GET | `/v1/rankings?limit=50` | Assets ordered by score, then symbol |

The ingestion endpoint is meant for local development. Add authentication, source licensing checks, rate limits, and production job scheduling before connecting a live provider. Historical bars and ranking results are not live prices.

## Tests

```sh
ruff check .
pytest -q
```

Tests use SQLite in memory for service and HTTP behavior. The Docker setup is the PostgreSQL path. CI runs lint and tests on each push and pull request.

## Extending providers

Implement `MarketDataProvider` in `providers/base.py` and pass it to `ingest`. Each provider must return sorted daily OHLCV bars with unique dates, use an accurate `name` identifying the source, and respect its own licensing and usage terms. No external project code or market data was copied into this repository.

