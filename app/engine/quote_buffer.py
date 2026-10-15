"""Bounded source+receipt observations; no price interpolation or future entry."""
import time
from collections import defaultdict,deque
class QuoteBuffer:
    def __init__(self,maxlen=1200):
        self._data = defaultdict(lambda:deque(maxlen=maxlen))
        self._last = {}
    def add(self,symbol,ts,price,received_ts=None):
        received = time.time() if received_ts is None else received_ts
        self._data[symbol].append((ts,price,received))
        self._last[symbol] = (ts,price)
    def last(self,symbol): return self._last.get(symbol)
    def last_price(self,symbol): return self._last[symbol][1] if symbol in self._last else None
    def last_ts(self,symbol): return self._last[symbol][0] if symbol in self._last else 0
    def age(self,symbol): return time.time()-self.last_ts(symbol) if symbol in self._last else float('inf')
    def at_or_before(self,symbol,target,tolerance):
        candidates = [(i,q) for i,q in enumerate(self._data.get(symbol,())) if 0<=target-q[0]<=tolerance and q[2]<=target]
        if not candidates: return None
        _,q = max(candidates,key=lambda pair:(pair[1][0],pair[1][2],pair[0]))
        return q[0],q[1]
    def last_received_ts(self,symbol):
        q=self._data.get(symbol)
        return q[-1][2] if q else None
    def recent(self,symbol,limit=10): return [(q[0],q[1]) for q in list(self._data.get(symbol,()))[-limit:]]
