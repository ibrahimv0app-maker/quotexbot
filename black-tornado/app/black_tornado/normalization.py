"""All signed transforms are bounded and price-scale invariant."""
import math,statistics

def clip(x,lo=-100.,hi=100.): return max(lo,min(hi,float(x)))
def signed(x): return 100*math.tanh(float(x))
def sign(x): return 1 if x>0 else (-1 if x<0 else 0)
def robust_z(value,history):
    if len(history)<10: return None
    m=statistics.median(history)
    mad=statistics.median(abs(x-m) for x in history)
    # Constant history gives no evidence of a standardized change; do not divide
    # by a fabricated epsilon or make a constant positive series look bearish.
    if mad==0: return 0.0 if value==m else (6.0 if value>m else -6.0)
    return clip((value-m)/(1.4826*mad),-6,6)
def percentile(value,history):
    if not history: return None
    return 100*(sum(x<value for x in history)+.5*sum(x==value for x in history))/len(history)
def weighted_available(values,weights):
    used={k:v for k,v in values.items() if v is not None}
    total=sum(weights[k] for k in used)
    return (sum(weights[k]*used[k] for k in used)/total if total else None),tuple(k for k,v in values.items() if v is None)
