# BLACK TORNADO v1.0 — mathematical and causal specification

## Inputs and bounded normalization

Default base window: the last 200 **complete, contiguous, minute-aligned** M1 bars available at the decision timestamp. Eight previous closed-bar frames each use their own same-length historical window, rather than repeatedly treating current-second observations as new M1 history. No forming candle's eventual OHLC is included. Source-bar hashes and configuration hashes travel with snapshots.

ATR-normalized distances remove instrument price scale. Signed transforms are bounded to −100…100. Rolling robust z-scores use the median and MAD of the previous reference window (default 60) using MAD×1.4826, capped at ±6. Zero MAD returns 0 for unchanged values or a bounded ±6 for a changed value; no fabricated epsilon is inserted. The implementation is `app/black_tornado/normalization.py`; scales and caps are heuristic research choices.

## Two directional domains

Let T_i and B_j be bounded signed family contributions and let w_i, v_j be their nonnegative intra-domain weights. Missing families are explicitly identified and dropped/reweighted **inside their own domain**, not converted into invented observations:

    T = sum(w_i T_i for available i) / sum(w_i for available i)
    B = sum(v_j B_j for available j) / sum(v_j for available j)
    BT_DIRECTION = 0.5 T + 0.5 B

Default T weights: trend .40, momentum .30, directional movement .20, oscillator transitions .10. Default B weights: structure .30, candle pressure .20, breakout/reclaim .20, rejection .10, exhaustion/divergence .10, closed HTF .10. Thus default overall contributions are respectively 20/15/10/5 and 15/10/10/5/5/5 percent. Missing data changes the effective within-domain weights; snapshots preserve original weights and missing-family names. A family's absence is distinct from a valid zero directional reading.

- **Trend:** combined EMA9/21/50 ordering, separation and all three slopes (.50/.30/.20),, normalized by ATR; related measures remain within one family.
- **Momentum:** RSI7/14, MACD histogram dynamics and ROC, grouped rather than each given an independent overall vote.
- **Directional movement:** signed DI separation, modulated by ADX strength. ADX alone has no bullish/bearish sign.
- **Oscillator transitions:** bounded RSI transition and a small centrally computed stochastic contribution, within the oscillator family.
- **Structure:** confirmed HH/HL or LH/LL; insufficient confirmed pivots are missing, mixed valid structure is neutral.
- **Pressure:** rolling combination of signed body/range and close location. `BT_PRESSURE` is the magnitude; signed pressure is preserved in features.
- **Breakout/reclaim:** bounded signed confirmed events, retests and failures, using ATR buffers. Price-only sweeps require penetration, reclaim and wick evidence.
- **Rejection:** wick geometry at previously confirmed structural levels.
- **Exhaustion/divergence:** directional rejection or confirmed-pivot price/pressure divergence, scaled by exhaustion. This is a price-behavior proxy, not volume divergence.
- **M5:** directional context from entirely closed aggregated M1 buckets, EMA21 and ATR. Incomplete/insufficient M5 data is disclosed and omitted, never padded or replaced with an unfinished close.

## Environment and consistency, not probability

ATR percentages and their historical ratio/percentile, BB-width percentile, true-range robust z-score, wick noise and direction flipping feed environment classifications. They do not acquire a bullish sign just because volatility rises.

    turbulence = clamp(35*range_spike + 25*TR_abnormality + 20*wick_noise + 20*flips, 0, 100)
    exhaustion = clamp(40*extension + 25*directional_wick + 20*pressure_decline + 15*divergence_present, 0, 100)
    confidence = clamp(100*(.30*family_sign_agreement + .30*domain_agreement
                            + .20*short_persistence + .20*known_nonchaotic_regime), 0, 100)

Each component is bounded as implemented in `core.py`. Family sign agreement uses nontrivial signed readings; domain agreement is `1−abs(T−B)/200`. **These formulas are correlated consistency heuristics, not estimates of P(win).** Confidence can be high without a sufficiently directional or eligible setup.

The deterministic regime classifier uses ordered tests for CHAOS, REVERSAL_RISK, SQUEEZE, EXPANSION, TREND_UP/DOWN and RANGE; otherwise UNKNOWN. Unknown/chaotic frames cannot generate eligible module candidates. Range recognition requires confirmed stable boundaries plus mean crossings and suitable ADX; it is not just “ADX is low.” Exact predicates and thresholds are versioned in code/config and tested for all eight labels.

## Causal structure and observations

A pivot at index i is known only after the configured right-side bars close; its `confirmed_ts` is stored. Event levels usable during a candle must be confirmed before that candle opens. Divergence compares two already-confirmed historical pivots, with pressure sampled from their historical positions. A later pivot is never backdated into an earlier frame.

Live frames carry decision time, genuine live source and receipt timestamps, live price, source-bar hash and parameters. Receipts after decision, negative source age, stale data, invalid/gapped/misaligned candles and insufficient warmup fail `BT_DATA_OK`. Closed-only research explicitly leaves `BT_DATA_OK=false`; separate research setup counting cannot create live eligible Candidates. The current frame and cached feature mappings are immutable; `snapshot()` returns an independent serializable copy.

REST candle history is the provider's current historical representation, **not a versioned archive of exactly what the server returned at each past second**. Offline causal-prefix tests cannot establish that a provider never revises historical OHLC. Forward persisted snapshots are the defensible record of actual observed state.

## Module interpretation and selection

Every module consumes a shared frame; none rebuilds a separate raw EMA/RSI strategy stack. Common gates: valid live data, supported regime, confidence ≥50, direction magnitude in candidate side ≥18, pressure ≥25, turbulence ≤70 and continuation extension ≤3 ATR (unless overridden by its configuration). Reversals additionally avoid a powerful still-unbroken opposing trend. A live price that has lost a breakout/pullback event level invalidates that candidate.

The ranker is a weighted suitability score, not another directional mixture. It combines direction, module trigger quality, behavior alignment, regime fit, turbulence suitability, M5 alignment and sufficiently sampled matching historical evidence. Missing M5/performance weights are dropped transparently. Beta smoothing applies only to eligible historical performance. There is no score-to-probability conversion.

Qualified opposing directions discard the pair. Within a symbol/direction/setup-family cluster, only the highest ranked candidate remains. A global selector ranks survivors and a transactional lifecycle lock permits at most one. A duplicate never adds score. Full module contracts are in STRATEGIES.md.
