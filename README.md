# 🌪️ BLACK TORNADO v1.0

**Signal-only, manual-entry research software. Paper mode is the default.**

This upgrade replaces the old five-strategy engine with **one shared BLACK TORNADO intelligence engine and exactly 25 interpretation modules**. PostgreSQL persistence, global lifecycle locking, asynchronous multi-connection market collection, FastAPI monitoring, Telegram delivery and Railway service configuration are retained. No Quotex account login, order placement, browser automation or broker execution is implemented.

## What the engine means

- Direction = **50% normalized technical domain + 50% normalized price-behavior domain**. This is NOT 50% per indicator.
- Technical family allocations: trend 20%, momentum 15%, directional movement 10%, oscillator transitions 5% of total direction.
- Behavior allocations: structure 15%, candle pressure 10%, breakout/reclaim 10%, rejection 5%, exhaustion/divergence 5%, closed M5 context 5%.
- `BT_DIRECTION`: −100…100. Confidence, pressure, turbulence and exhaustion: 0…100. **Confidence and BT ranking score are heuristics, not win probabilities.**
- ATR, Bollinger width and true-range abnormalities describe conditions, not bullish/bearish votes. Correlated indicators are grouped; 25 module triggers are not 25 independent confirmations.
- Pivots become usable only after confirmation. M5 is assembled exclusively from complete closed M1 buckets. Current candle's eventual OHLC is never used at the notification timestamp.
- OHLC sweeps and reclaims are **price-only proxies**, not measured institutional order flow or liquidity.

Mathematics: [docs/ENGINE.md](docs/ENGINE.md). All module rules and parameters: [docs/STRATEGIES.md](docs/STRATEGIES.md). Evidence and caveats: [docs/VALIDATION.md](docs/VALIDATION.md).

## Quick start

Python 3.13 recommended; PostgreSQL 17 is used in the supplied CI/integration tests.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Edit DATABASE_URL; leave DRY_RUN=true. Never put credentials into source control.
python -m app.main
```

For a local PostgreSQL + application container stack:

```bash
docker compose up --build
```

Docker configuration is supplied but **was not built in this environment**. Do not expose the example local database credentials on a public database. Only Railway's persistent service—not this temporary workspace preview—removes personal-computer uptime dependence.

### Monitoring

- `/health`: database, scanner and paper/live mode; HTTP readiness is not proof all documented symbols work.
- `/health/feeds`: per-symbol availability, freshness, source status and stream connections.
- `/stats`: ranking/rejection/cadence diagnostics, active lock, persisted signals; `black_tornado_outcomes` isolates this engine and current paper/live delivery scope. `outcomes` intentionally retains the all-history administrative view.
- `/stats/strategies`: forward feed-estimated samples, **not** validated historical ranking inputs.
- `POST /admin/pause/true` with `Authorization: Bearer <ADMIN_API_KEY>` pauses new signals; existing outcomes continue. `/false` resumes unless `KILL_SWITCH=true`.

## Timing and one-signal lifecycle

M1 analysis, next-minute entry, 60-second expiry, Asia/Karachi display. Default lead is 12 seconds; actual Telegram send must begin 10–15 seconds before entry. Missed windows are canceled. All eligible pairs are compared; opposing qualified directions discard that pair and correlated same-family candidates are deduplicated without vote inflation. Default minimum ranking score is 75.

A PostgreSQL transaction and persistent singleton lock allow **at most one unresolved lifecycle globally**, and unique entry-slot protection survives restart. Entry/expiry prices must be actual recorded observations at/before their boundary, within the configured tolerance, and locally received by the boundary. Missing observations become `UNVERIFIED`, never synthetic closes. Result settlement releases the lock only after transactional completion.

Telegram has no send idempotency key: this implementation deliberately permits **one durable send attempt**, not an exactly-once guarantee. An ambiguous crash may omit a message rather than resend a duplicate. Restart recovery tests cover the persisted state machine, not every possible Telegram/network failure.

## Requested boxed Telegram format

Illustrative format only; pair, direction, entry time, score, setup and ID are populated from the actual selected signal, not these example constants:

```text
╔══ 🌑 BLACK TORNADO ══╗
      🚨 SIGNAL DETECTED

PAIR: EURUSD-OTC
TRADE: 🟢 CALL
TIME: 12:13:00 PKT
EXP: 60 SECONDS
BT SCORE: 82/100
SETUP: PULLBACK RECLAIM

╚══════ #BT001 ══════╝
```

PUT uses `🔴 PUT`. IDs use the database's durable sequence, growing beyond three digits without reset. `PULLBACK RECLAIM` is the display label for BT03; other setups use the selected module's readable name. Default result:

```text
╔══ 🌑 BLACK TORNADO ══╗
          RESULT

PAIR: EURUSD-OTC
TRADE: 🟢 CALL

✅ WIN
⚠️ Result: Feed-estimated

╚══════ #BT001 ══════╝
```

Losses show `❌ LOSS`; flat outcomes show `➖ DRAW`. Missing observations show `❔ UNVERIFIED` with a reason, **never an invented WIN/LOSS**. Result and signal carry the same durable ID. Compact results no longer include cumulative statistics; these remain in PostgreSQL and `/stats`. `TELEGRAM_INCLUDE_AUDIT_DETAILS=true` optionally adds actual prices/statistics and audit detail. Feed estimates are not independently confirmed Quotex account outcomes.

### Real Telegram delivery test completed

An authorized, clearly labeled TEST signal and TEST result were accepted by Telegram on 2026-10-15: message IDs **27926** and **27927**, in the configured channel. Bot administrator/posting permission was checked first. Result was UNVERIFIED (delivery test only), not a fabricated market win. No trade/statistics row was created. Receipt is in `evidence/telegram-delivery-test.json` in the full evidence package.

To explicitly repeat a labeled test using your securely configured environment:

```bash
python -m app.cli telegram-test --send
```

This command sends **two TEST messages**, even if paper mode is enabled, because `--send` explicitly authorizes the delivery test. It does not test natural market selection, broker execution or actual boundary settlement. Full publication/settlement paths are also integration-tested with synthetic fixtures and mock Telegram transport on SQLite/PostgreSQL. No test signal is sent automatically on startup or restart.

## Configuration

`black_tornado_settings.json` controls indicator periods, normalization windows, structure/regime definitions and intra-domain family weights. Each domain's weights must sum to 1; the outer 50/50 split is fixed. `strategy_settings.json` controls per-module thresholds. `BT_ENABLED_STRATEGIES` supports a subset or an empty list; all 25 research modules are present and enabled by default in **paper** mode. Defaults are unvalidated hypotheses, not 25 production-approved strategies.

`.env.example` documents environment settings. Important controls: `DRY_RUN`, `KILL_SWITCH`, `SYMBOLS`, `MIN_SETUP_SCORE`, `BT_MAX_TURBULENCE`, `BT_MIN_CONFIDENCE`, `BT_MIN_DIRECTION`, `STREAM_TRANSPORT` and notification-window/quote-tolerance settings. Do not weaken gates to create a signal quota.

The ranker uses 20 direction + 25 trigger + 15 behavior + 10 regime compatibility + 15 turbulence suitability + 5 M5 alignment + 10 eligible historical performance. Missing M5/performance components are explicitly dropped and available weights rescaled. These components remain correlated and are not statistical independence claims.

A performance artifact is optional. It must be a completed tick-replay test artifact with the same engine/core/module configuration hash and at least `MIN_PERFORMANCE_SAMPLE` wins+losses per pair/module. Current evidence is insufficient: the supplied OOS artifacts are empty and no performance boost is earned. Forward `/stats/strategies` data is not silently substituted.

## Real-data tools

The existing feed remains `https://quotexfeed.lovable.app`, with its public documentation at `/docs`. Canonical identifiers are preserved. The collector opens groups of at most ten symbols per stream connection; unavailable symbols are excluded independently and periodically retried.

```bash
python -m app.cli diagnose --all --seconds 20 --limit 2001 --output evidence/my-diagnostic
python -m app.cli diagnose --all --seconds 600 --limit 2001 --output evidence/my-capture
python -m app.cli backtest --candles evidence/my-capture/candles.json \
  --quotes evidence/my-capture/quotes.jsonl --output evidence/my-replay
python -m app.cli validate --candles evidence/my-capture/candles.json \
  --quotes evidence/my-capture/quotes.jsonl --output evidence/my-validation
```

Without `--quotes`, replay counts **closed-candle research setups only**: it does not pass the live data gate, fabricate boundary prices or produce a verified win rate. Every replay writes a global report and separate BT01…BT25 reports. The validation command uses expanding chronological slices, frozen sensitivity probes and explicit multiplicity warnings; it does not train or optimize a predictive model.

## Tests

```bash
TEST_POSTGRES_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/TEST_DB python -m pytest -q
python -m compileall -q app tests
```

**Use a disposable test database: integration fixtures drop their schema.** Without `TEST_POSTGRES_URL`, PostgreSQL cases skip; SQLite tests alone do not validate PostgreSQL locking. The supplied completed run used a real disposable PostgreSQL database. Synthetic rule-contract tests prove conditions and symmetry, not profitability.

## Railway deployment

Quick GitHub → Railway steps: [QUICK_DEPLOY.md](QUICK_DEPLOY.md). Operational detail: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). A Dockerfile, `railway.toml`, GitHub CI and Compose file are supplied. Railway deployment, Docker build and independent Quotex price comparison remain untested; real labeled Telegram delivery was tested. Start with `DRY_RUN=true`; observe long enough to obtain legitimate paper lifecycles before enabling Telegram.

This software makes no profitability, accuracy, payout, fill-quality or production-readiness guarantee. There is no ML/NN added simply to imply intelligence. Trading binary options involves substantial risk.
