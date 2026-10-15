# BLACK TORNADO — exactly 25 module contracts

All modules consume one shared BT frame. Common live gates, score semantics and global deduplication are defined in ENGINE.md. The predicates below are the executable confirmation conditions, not independent raw-indicator stacks. Default thresholds are hypotheses; changing thresholds requires new validation, not a profitability claim.

Universal invalidations: BT_DATA_OK false; unsupported regime; insufficient directional magnitude, pressure or confidence; turbulence above threshold; overextended continuation; powerful unbroken opposing trend for reversal; invalidated live breakout/pullback level; late entry window; active global lifecycle; insufficient final ranking score. No signal is required.

Independent historical and held-out results for each module: `evidence/historical-reports/BTxx/report.json` and `evidence/tick-reports/BTxx/report.json`. Missing outcome samples stay zero with null win rates. Positive/negative trigger-contract fixtures and structural direction symmetry tests are in `tests/test_black_tornado_strategies.py`; these synthetic tests are not measured trading performance.

| ID | Interpretation | Sides | Setup family |
|---|---|---|---|
|BT01|TORNADO_IGNITION|CALL,PUT|breakout|
|BT02|MAIN_TORNADO_TREND|CALL,PUT|continuation|
|BT03|ADAPTIVE_PULLBACK|CALL,PUT|pullback|
|BT04|SHALLOW_RETRACEMENT|CALL,PUT|continuation|
|BT05|STORM_ACCELERATION|CALL,PUT|continuation|
|BT06|FRESH_STRUCTURE_BREAKOUT|CALL,PUT|breakout|
|BT07|BREAKOUT_RETEST|CALL,PUT|pullback|
|BT08|SQUEEZE_RELEASE|CALL,PUT|breakout|
|BT09|FIRST_IMPULSE_AFTER_COMPRESSION|CALL,PUT|breakout|
|BT10|M5_M1_ALIGNMENT|CALL,PUT|continuation|
|BT11|SWEEP_AND_RECLAIM|CALL,PUT|reclaim|
|BT12|FAILED_BREAKOUT_TRAP|CALL,PUT|reclaim|
|BT13|STRUCTURAL_WICK_REJECTION|CALL,PUT|reversal|
|BT14|EXHAUSTION_DIVERGENCE|CALL,PUT|reversal|
|BT15|OVEREXTENSION_SNAPBACK|CALL,PUT|reversal|
|BT16|RANGE_FLOOR_BOUNCE|CALL,PUT|range|
|BT17|RANGE_CEILING_FADE|CALL,PUT|range|
|BT18|MEAN_REVERSION_RETURN|CALL,PUT|range|
|BT19|DOUBLE_SWEEP_TRAP|CALL,PUT|reclaim|
|BT20|FAILED_CONTINUATION_FLIP|CALL,PUT|reversal|
|BT21|SPIKE_COOLDOWN_CONTINUATION|CALL,PUT|cooldown|
|BT22|SPIKE_EXHAUSTION_REVERSAL|CALL,PUT|reversal|
|BT23|CANDLE_PRESSURE_SEQUENCE|CALL,PUT|continuation|
|BT24|TREND_TO_RANGE_TRANSITION|CALL,PUT|range|
|BT25|RANGE_TO_TREND_TRANSITION|CALL,PUT|breakout|

## BT01 — TORNADO_IGNITION

Fresh directional ignition following range/compression.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"ignition_direction": 35.0, "ignition_pressure": 40.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        transition=any(p.BT_REGIME in ('RANGE','SQUEEZE') for p in bt.previous[-3:])
        ok=transition and bt.features.get('breakout_side')==side and side*bt.BT_DIRECTION>=p['ignition_direction'] and bt.BT_PRESSURE>=p['ignition_pressure']
        return ok,.95,'fresh breakout from range/squeeze' if ok else 'no confirmed ignition transition'
```

## BT02 — MAIN_TORNADO_TREND

Established BT direction with retained structure.

Supported regimes: TREND_UP, TREND_DOWN. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "sustained_direction": 40.0, "trend_pressure": 45.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        persistence=len(bt.previous)>=2 and all(self.trend(x,side) and side*x.BT_DIRECTION>=p['sustained_direction'] for x in bt.previous[-2:])
        ok=self.trend(bt,side) and persistence and side*bt.BT_DIRECTION>=p['sustained_direction'] and bt.BT_PRESSURE>=p['trend_pressure'] and bt.features.get('structure_held_side')==side and not bt.features.get('failed_breakout_side')
        return ok,.9,'persistent trend with intact structure' if ok else 'trend persistence/structure absent'
```

## BT03 — ADAPTIVE_PULLBACK

Trend pullback to the adaptive mean followed by rejection.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "pullback_distance": 1.0, "recovery": 4.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        near=any(x.features.get('mean_distance_atr',999)<=p['pullback_distance'] for x in bt.previous[-3:])
        ok=prev is not None and near and bt.features.get('mean_rejection_side')==side and bt.features.get('ema_trend_side')==side and self.rising(bt,side,p['recovery'])
        return ok,.95,'adaptive-mean pullback rejected with pressure recovery' if ok else 'no mean pullback and recovery'
```

## BT04 — SHALLOW_RETRACEMENT

Small counter-candle and resumed established trend.

Supported regimes: TREND_UP, TREND_DOWN. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "pressure_recovery": 5.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        ok=prev is not None and bt.features.get('shallow_retracement_side')==side and bt.features.get('structure_held_side')==side and self.pressure(bt,side)>self.pressure(prev,side)+p['pressure_recovery']
        return ok,.9,'shallow counter-move held structure and resumed' if ok else 'shallow retracement not confirmed'
```

## BT05 — STORM_ACCELERATION

Increasing direction and pressure without chasing excess extension.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"direction_acceleration": 12.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        seq=list(bt.previous[-2:])+[bt]
        ok=len(seq)==3 and all(side*seq[i].BT_DIRECTION>side*seq[i-1].BT_DIRECTION for i in (1,2)) and side*(seq[-1].BT_DIRECTION-seq[0].BT_DIRECTION)>=p['direction_acceleration'] and all(self.pressure(seq[i],side)>self.pressure(seq[i-1],side) for i in (1,2))
        return ok,.95,'three closed observations show accelerating direction and pressure' if ok else 'acceleration sequence absent'
```

## BT06 — FRESH_STRUCTURE_BREAKOUT

A fresh, not aged, confirmed structural break.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"break_body": 0.5, "break_direction": 35.0, "max_extension": 3, "max_turbulence": 70, "min_break_distance": 0.1, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        distance=bt.features.get('breakout_distance_atr',0)
        ok=bt.features.get('breakout_side')==side and distance>=p['min_break_distance'] and side*bt.BT_DIRECTION>=p['break_direction'] and bt.features.get('body_ratio',0)>=p['break_body']
        return ok,.95,'fresh confirmed-level break with displacement' if ok else 'no fresh qualified structure break'
```

## BT07 — BREAKOUT_RETEST

Revisit of a previously broken level, with hold and resumption.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_retest_age": 5.0, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "retest_recovery": 4.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prior=bt.features.get('prior_breakout')
        ok=bool(prior and 1<=prior['age']<=p['max_retest_age'] and prior['breakout']==side and bt.features.get('retest_side')==side and self.rising(bt,side,p['retest_recovery']))
        return ok,.95,'known breakout retested, accepted and pressure renewed' if ok else 'retest/acceptance not confirmed'
```

## BT08 — SQUEEZE_RELEASE

Compression gives way to a structural release.

Supported regimes: EXPANSION, TREND_UP, TREND_DOWN. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "release_pressure": 45.0, "release_range": 1.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        compressed=any(x.BT_REGIME=='SQUEEZE' or x.features.get('compression') for x in bt.previous[-3:])
        ok=compressed and bt.features.get('breakout_side')==side and bt.BT_PRESSURE>=p['release_pressure'] and bt.features.get('range_atr',0)>=p['release_range']
        return ok,.95,'compression released through structure with directional pressure' if ok else 'no confirmed squeeze release'
```

## BT09 — FIRST_IMPULSE_AFTER_COMPRESSION

First directional body after compression, not a late impulse.

Supported regimes: EXPANSION, TREND_UP, TREND_DOWN. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"impulse_body": 0.65, "impulse_max": 2.2, "impulse_min": 1.2, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "quiet_range": 1.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prior=list(bt.previous[-3:])
        quiet=len(prior)==3 and all(x.features.get('range_atr',999)<=p['quiet_range'] for x in prior) and any(x.BT_REGIME in ('SQUEEZE','RANGE') for x in prior)
        ok=quiet and bt.features.get('breakout_side')==side and p['impulse_min']<=bt.features.get('range_atr',0)<=p['impulse_max'] and bt.features.get('body_ratio',0)>=p['impulse_body']
        return ok,.95,'first bounded impulse after confirmed compression' if ok else 'late/unconfirmed first impulse'
```

## BT10 — M5_M1_ALIGNMENT

Fully closed M5 context agrees with M1 trend.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"alignment_body": 0.45, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        ok=prev is not None and self.aligned(bt,side) and bt.features.get('resume_side')==side and bt.features.get('body_ratio',0)>=p['alignment_body'] and self.pressure(bt,side)>self.pressure(prev,side)
        return ok,.9,'closed M5 agreement plus fresh M1 continuation trigger' if ok else 'no aligned M1 continuation trigger'
```

## BT11 — SWEEP_AND_RECLAIM

A price sweep closes back inside a confirmed level.

Supported regimes: RANGE, REVERSAL_RISK, EXPANSION, TREND_UP, TREND_DOWN. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "reclaim_pressure": 25.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        ok=bt.features.get('sweep_side')==side and self.pressure(bt,side)>=p['reclaim_pressure'] and bt.features.get('rejection_side')==side
        return ok,.95,'price-only sweep proxy reclaimed known level with rejection' if ok else 'no structural sweep/reclaim confirmation'
```

## BT12 — FAILED_BREAKOUT_TRAP

A prior breakout fails and pressure confirms the opposite side.

Supported regimes: RANGE, REVERSAL_RISK, EXPANSION. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "trap_shift": 12.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prior=bt.features.get('prior_breakout')
        ok=bool(prior and prior['breakout']==-side and bt.features.get('failed_breakout_side')==side and self.rising(bt,side,p['trap_shift']))
        return ok,.95,'prior breakout failed and BT shifted to opposite side' if ok else 'known breakout failure/shift absent'
```

## BT13 — STRUCTURAL_WICK_REJECTION

Structural wick rejection with direction already confirming.

Supported regimes: RANGE, REVERSAL_RISK, EXPANSION. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "rejection_pressure": 25.0, "structural_wick": 0.4}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        wick=bt.features.get('lower_wick' if side==1 else 'upper_wick',0)
        ok=bt.features.get('rejection_side')==side and wick>=p['structural_wick'] and self.pressure(bt,side)>=p['rejection_pressure']
        return ok,.9,'confirmed structure rejected with opposing wick/body pressure' if ok else 'no meaningful structural rejection'
```

## BT14 — EXHAUSTION_DIVERGENCE

Confirmed pivot divergence plus rejection; no future pivot.

Supported regimes: RANGE, REVERSAL_RISK, EXPANSION. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"divergence_exhaustion": 50.0, "divergence_shift": 8.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        pivots=bt.features.get('divergence_pivots',[])
        confirmed=len(pivots)==2 and all(x['confirmed_ts']<=bt.closed_through for x in pivots)
        ok=confirmed and bt.features.get('divergence_side')==side and bt.BT_EXHAUSTION>=p['divergence_exhaustion'] and side*bt.features.get('body_signed',0)>0 and self.rising(bt,side,p['divergence_shift'])
        return ok,.95,'confirmed pivots diverge from historical BT pressure; reversal confirmed' if ok else 'confirmed-pivot divergence/reversal absent'
```

## BT15 — OVEREXTENSION_SNAPBACK

Extended price begins returning toward its mean.

Supported regimes: RANGE, REVERSAL_RISK. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "snapback_displacement": 2.0, "snapback_exhaustion": 65.0, "snapback_shift": 5.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        ok=bt.features.get('range_valid',False) and side*bt.features.get('deviation_atr',0)<=-p['snapback_displacement'] and bt.BT_EXHAUSTION>=p['snapback_exhaustion'] and bt.features.get('resume_side')==side and self.rising(bt,side,p['snapback_shift'])
        return ok,.95,'extended range move exhausted with confirmed return pressure' if ok else 'no safe overextension snapback'
```

## BT16 — RANGE_FLOOR_BOUNCE

Floor-specific range rejection; CALL only.

Supported regimes: RANGE. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"floor_location": 0.2, "floor_recovery": 5.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        loc=bt.features.get('range_location')
        ok=side==1 and bt.features.get('range_valid',False) and loc is not None and loc<=p['floor_location'] and bt.features.get('rejection_side')==1 and self.rising(bt,1,p['floor_recovery'])
        return ok,.9,'validated range floor rejected with bullish recovery' if ok else 'no confirmed range-floor bounce'
```

## BT17 — RANGE_CEILING_FADE

Ceiling-specific range rejection; PUT only.

Supported regimes: RANGE. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"ceiling_location": 0.8, "ceiling_recovery": 5.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        loc=bt.features.get('range_location')
        ok=side==-1 and bt.features.get('range_valid',False) and loc is not None and loc>=p['ceiling_location'] and bt.features.get('rejection_side')==-1 and self.rising(bt,-1,p['ceiling_recovery'])
        return ok,.9,'validated range ceiling rejected with bearish recovery' if ok else 'no confirmed range-ceiling fade'
```

## BT18 — MEAN_REVERSION_RETURN

A controlled return from range extension toward the mean.

Supported regimes: RANGE. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "return_displacement": 1.5, "return_shift": 5.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        loc=bt.features.get('range_location')
        ok=prev is not None and bt.features.get('range_valid',False) and loc is not None and 0<=loc<=1 and side*prev.features.get('deviation_atr',0)<=-p['return_displacement'] and abs(bt.features.get('deviation_atr',0))<abs(prev.features.get('deviation_atr',0)) and self.rising(bt,side,p['return_shift'])
        return ok,.9,'extended range price re-entered toward adaptive mean' if ok else 'mean return/re-entry absent'
```

## BT19 — DOUBLE_SWEEP_TRAP

Repeated same-side sweeps of the same approximate level.

Supported regimes: RANGE, REVERSAL_RISK, EXPANSION. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"double_pressure": 30.0, "double_shift": 5.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        ok=bt.features.get('double_sweep_side')==side and bt.features.get('sweep_side')==side and self.pressure(bt,side)>=p['double_pressure'] and self.rising(bt,side,p['double_shift'])
        return ok,.95,'two failed penetrations at same boundary; opposite reclaim proxy' if ok else 'double sweep/reclaim not confirmed'
```

## BT20 — FAILED_CONTINUATION_FLIP

Prior directional continuation fails and BT flips.

Supported regimes: REVERSAL_RISK, EXPANSION, RANGE. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"flip_pressure": 30.0, "flip_shift": 15.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "prior_continuation": 30.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        prior=any((-side*x.BT_DIRECTION)>=p['prior_continuation'] and x.BT_REGIME in ('TREND_UP','TREND_DOWN','EXPANSION') for x in bt.previous[-3:])
        structural=bt.features.get('failed_breakout_side')==side or bt.features.get('breakout_side')==side
        ok=prev is not None and prior and structural and self.pressure(bt,side)>=p['flip_pressure'] and self.rising(bt,side,p['flip_shift'])
        return ok,.95,'continuation pressure failed; opposite structural confirmation' if ok else 'continuation failure/flip not confirmed'
```

## BT21 — SPIKE_COOLDOWN_CONTINUATION

A previous spike cools down before trend continuation.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"cooldown_age": 6.0, "cooldown_drop": 15.0, "cooldown_pressure": 45.0, "max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        age=bt.features.get('last_spike_age')
        peak=max((x.BT_TURBULENCE for x in bt.previous[-6:]),default=0)
        ok=age is not None and 2<=age<=p['cooldown_age'] and peak-bt.BT_TURBULENCE>=p['cooldown_drop'] and bt.features.get('structure_held_side')==side and bt.features.get('ema_trend_side')==side and bt.BT_PRESSURE>=p['cooldown_pressure']
        return ok,.9,'post-spike turbulence normalized; original structure and pressure hold' if ok else 'spike cooldown continuation not confirmed'
```

## BT22 — SPIKE_EXHAUSTION_REVERSAL

An exhausted spike produces confirmed opposite pressure.

Supported regimes: REVERSAL_RISK, RANGE, EXPANSION. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "spike_exhaustion": 65.0, "spike_reversal_age": 5.0, "spike_shift": 8.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        age=bt.features.get('last_spike_age')
        evidence=bt.features.get('failed_breakout_side')==side or bt.features.get('sweep_side')==side or bt.features.get('rejection_side')==side
        ok=age is not None and 1<=age<=p['spike_reversal_age'] and evidence and bt.BT_EXHAUSTION>=p['spike_exhaustion'] and self.rising(bt,side,p['spike_shift'])
        return ok,.95,'post-spike failed extension/rejection plus reversal confirmation' if ok else 'spike alone is not reversal evidence'
```

## BT23 — CANDLE_PRESSURE_SEQUENCE

A clean multi-candle pressure sequence in the BT direction.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "sequence_pressure": 60.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        prev=self.previous(bt)
        no_conflict=bt.features.get('failed_breakout_side',0)!=-side and bt.features.get('rejection_side',0)!=-side
        ok=prev is not None and bt.features.get('body_sequence_side')==side and self.pressure(bt,side)>=p['sequence_pressure'] and self.pressure(bt,side)>self.pressure(prev,side) and no_conflict
        return ok,.95,'three strong directional bodies and close positions; pressure growing' if ok else 'directional pressure sequence incomplete'
```

## BT24 — TREND_TO_RANGE_TRANSITION

An established trend transitions into a bounded range.

Supported regimes: RANGE. Reversal safeguards: yes.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "range_transition_shift": 5.0, "transition_pressure_drop": 15.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        old=[x for x in bt.previous[-5:] if x.BT_REGIME in ('TREND_UP','TREND_DOWN')]
        ok=bool(old) and bt.features.get('range_valid',False) and old[-1].BT_PRESSURE-bt.BT_PRESSURE>=p['transition_pressure_drop'] and bt.features.get('rejection_side')==side and self.rising(bt,side,p['range_transition_shift'])
        return ok,.9,'trend pressure faded into validated range; boundary rejection confirmed' if ok else 'weak trend alone does not establish range transition'
```

## BT25 — RANGE_TO_TREND_TRANSITION

A bounded range transitions into confirmed directional expansion.

Supported regimes: TREND_UP, TREND_DOWN, EXPANSION. Reversal safeguards: continuation safeguards.

Parameters (including common preconditions):
```json
{"max_extension": 3, "max_turbulence": 70, "min_confidence": 50, "min_direction": 18, "min_pressure": 25, "range_observations": 2.0, "transition_expansion": 1.1, "transition_pressure": 50.0}
```

Confirmation, trigger quality and rejection reason (executable contract):
```python
def trigger(self, bt, side):
        p=self.parameters
        range_history=sum(x.BT_REGIME=='RANGE' and x.features.get('range_valid',False) for x in bt.previous[-4:])
        ok=range_history>=p['range_observations'] and bt.features.get('breakout_side')==side and bt.features.get('atr_norm',0)>=p['transition_expansion'] and bt.BT_PRESSURE>=p['transition_pressure'] and not bt.features.get('failed_breakout_side')
        return ok,.95,'established range broke with expansion and directional pressure' if ok else 'range-to-trend transition not confirmed'
```
