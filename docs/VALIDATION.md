# BLACK TORNADO v1.0 — validation evidence

## What was actually executed

- Full automated suite: **348 passed**, with SQLite and real PostgreSQL cases; no PostgreSQL skips in the recorded run. Compile checks passed. Synthetic trigger tests are contract tests, not trading evidence.
- Fresh public API diagnostic: 39 of 48 documented symbols had history and streaming observations. The collector uses five groups, each at most ten symbols. The nine empty symbols are not permanently blacklisted.
- Real historical setup replay: three pairs (EURUSD-OTC, GBPUSD-OTC, USDPKR-OTC), 2,001 provider M1 candles each. Current provider history is not a versioned as-of archive.
- Genuine receipt-timestamped tick replays: the retained short original capture and the new BLACK TORNADO PostgreSQL paper-service export. Both reuse the new engine, not old strategy results.
- Expanding chronological validation: three windows on a separate 600-bar real EURUSD slice. Independent test metrics are emitted for all 25 modules. This is a slice/replay study, not fitted ML.
- Frozen sensitivity grid: regime trend-direction threshold 30, 35, 40; validation-only reporting. There is no final-test-driven threshold selection. Train/validation decisions whose expiry plus maximum resolution timeout crosses the next split are purged.
- Local long-running paper HTTP service with PostgreSQL, all configured feed groups and controlled restarts. No Quotex order was made. Subsequently, two authorized, explicitly labeled Telegram delivery-test messages were sent (see below). A restart with an actual unresolved **new** live BT lifecycle was not observed; state-machine recovery is covered by integration tests.

## Outcomes: insufficient evidence, not a win-rate claim

Closed-candle research setups across three pairs: **621**. These lack historical decision/boundary ticks, cannot pass the live gate and are **not trades**.

Retained genuine-tick replay: 0 raw module setups; 0 eligible selected signals. New forward-tick replay: 1 raw setups; 0 eligible selected signals. **No resolved directional performance sample; all win rates remain null/N/A.** No module receives an OOS ranking boost, and no module is certified profitable.

The short captured market periods do not cover every regime, notification slot or outcome boundary. A zero count says nothing about profitability. Closed-only setups also omit live quote invalidation/freshness and the final eligibility/ranking filters. No invented notification prices, OHLC-to-tick interpolation or eventual current-candle close was used.

### Independent module research counts

| Module | Train setups | Validation setups | Test setups | Verified outcome sample |
|---|---:|---:|---:|---:|
|BT01|7|1|4|0|
|BT02|12|4|14|0|
|BT03|8|5|2|0|
|BT04|25|9|9|0|
|BT05|82|26|24|0|
|BT06|45|17|18|0|
|BT07|25|11|12|0|
|BT08|4|1|2|0|
|BT09|3|0|0|0|
|BT10|129|44|42|0|
|BT11|0|1|0|0|
|BT12|6|1|2|0|
|BT13|1|0|0|0|
|BT14|0|1|2|0|
|BT15|0|0|0|0|
|BT16|0|0|0|0|
|BT17|0|0|0|0|
|BT18|0|0|0|0|
|BT19|0|0|0|0|
|BT20|1|0|0|0|
|BT21|3|0|0|0|
|BT22|0|0|0|0|
|BT23|9|3|4|0|
|BT24|0|0|0|0|
|BT25|0|1|1|0|

Counts are correlated research hypotheses and must not be summed as independent confirmations. Every module has its own report directory, even with zero setups. Per-pair and per-split research counts are in `setup_counts`; outcome grouping, longest losing streak and sample denominators are in JSON reports when outcome samples exist.

## Multiple testing and promotion gate

There are 25 correlated strategy hypotheses, many thresholds and repeated opportunities to overfit. Even a naive 25-test family at nominal 0.05 would need at least 0.002 per comparison under Bonferroni; this is an explanatory warning, **not** a statistical significance calculation on these data. A proper future study needs a registered hypothesis/parameter set, longer receipt-timestamped observations, untouched held-out periods, realistic delivery latency, pair/regime samples and forward review. No optimization or automatic promotion is implemented.

Performance artifacts require tick replay, completed test split, matching engine/core/module hash, matching pair/module, a test end strictly before decision and at least the configured directional sample size. Paper/live channel aggregates are kept separate and are not treated as independent OOS proof.

## Evidence map

- `test-results.log`: completed full suite.
- `evidence/api-current/`: current provider documentation, diagnostic, actual candles and actual ticks.
- `evidence/historical-input.json`, `historical-reports/`: three-pair candle-only research; global plus 25 independent reports.
- `evidence/recorded-replay/`, `tick-reports/`: retained genuine ticks, replayed with BLACK TORNADO; no inherited old performance claims.
- `evidence/forward-paper/`, `forward-tick-reports/`: actual local paper-service database export and fresh tick replay. `signals.json` has no selected BT alerts in this short observation.
- `evidence/forward-paper/reconstructed-rejected-frame.json`: an offline reconstruction demonstrating stale-history rejection, **not** an originally published decision snapshot. Provider revision/as-of limits still apply.
- `evidence/walk-forward/validation.json`: three expanding windows, all-module held-out metrics and validation-only sensitivity.
- `evidence/runtime-*.json`, `runtime.log`: local feed/health/cadence and restart observations.

## Operational and external limits

Some startup/CPU-contention cycles exceeded the one-second budget; no universal hard real-time claim is made. Inspect recorded `overruns`, current `cycle_ms` and feed readiness. Stable warm-cache latency is not a worst-case guarantee. No signal was forced during this short paper run. Full decision snapshot persistence is wired and tested through the infrastructure, but no naturally selected forward BT alert/outcome lifecycle was available in this observation.

Not exercised externally: Railway deployment, Docker build, GitHub-hosted workflow, sustained outage/restart under real Telegram ambiguity, comparison to real Quotex account prices/payouts/fills. Feed-estimated results must always retain their disclaimer. Schema creation is not a general migration system; versioned as-of candle/tick object-store archival is not supplied.

## Authorized Telegram delivery test — 2026-10-15

Production formatter + TelegramClient + actual Telegram Bot API were exercised against the user-authorized channel. Bot administrator and posting permission were verified. TEST signal acknowledgement: message 27926; TEST result acknowledgement: message 27927. The result was explicitly UNVERIFIED because there was no trade or boundary-price settlement. No result, price or win-rate performance was fabricated; no trade rows were created. Raw safe receipt: `evidence/telegram-delivery-test.json`.

The updated 348-test suite additionally exercises the full persistent publication → send claim → signal acknowledgement → synthetic boundary settlement → result acknowledgement → lock release path against SQLite and PostgreSQL with a mock Telegram transport. This plus the real delivery test does not establish profitability or a naturally selected real-market end-to-end lifecycle.
