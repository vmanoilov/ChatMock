# chatmock/rate_limit.py
from __future__ import annotations

import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Optional

from .config import CHATMOCK_QUEUE_TIMEOUT, CHATMOCK_RATE_LIMIT_RPS

class GateBusy(Exception):
    """Queue is full; caller should back off."""
    def __init__(self, retry_after_seconds: int = 2):
        super().__init__("Server busy")
        self.retry_after_seconds = int(retry_after_seconds)


class TokenBucket:
    """Simple token bucket rate limiter."""
    def __init__(self, rate_per_second: float, burst: int):
        self.rate = rate_per_second
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

class _Permit:
    def __init__(self, gate: "Gate"):
        self._gate = gate
        self._released = False
    def release(self):
        if not self._released:
            self._released = True
            self._gate._release()

class Gate:
    """
    Fair, bounded concurrency gate with RPS rate limiting.
    - max_concurrency: number of simultaneous upstream requests allowed.
    - queue_limit: max number of waiters; beyond this we reject with 429 + Retry-After.
    - rate_limiter: optional TokenBucket for RPS limiting.
    """
    def __init__(self, max_concurrency: int = 1, queue_limit: int = 100, rate_limiter: Optional[TokenBucket] = None):
        self.max = max(1, int(max_concurrency))
        self.qmax = max(0, int(queue_limit))
        self.rate_limiter = rate_limiter
        self._lock = threading.Lock()
        self._permits = self.max
        self._waiters = deque()

    def acquire(self, *, wait_timeout: Optional[float] = None) -> _Permit:
        """Acquire a permit or wait fairly. Raise GateBusy if queue is full or rate limited."""
        # Check rate limiter first
        if self.rate_limiter and not self.rate_limiter.acquire():
            raise GateBusy(retry_after_seconds=1)  # Rate limited

        ev = None
        with self._lock:
            if self._permits > 0 and not self._waiters:
                self._permits -= 1
                return _Permit(self)
            if len(self._waiters) >= self.qmax:
                raise GateBusy(retry_after_seconds=2)
            ev = threading.Event()
            self._waiters.append(ev)
        signaled = ev.wait(timeout=wait_timeout)
        if not signaled:
            # timed out; withdraw from queue if still present
            with self._lock:
                try:
                    self._waiters.remove(ev)
                except ValueError:
                    pass
            raise GateBusy(retry_after_seconds=2)
        # we were granted a permit
        return _Permit(self)

    def _release(self):
        with self._lock:
            if self._waiters:
                ev = self._waiters.popleft()
                # Do not decrement permits, just hand off directly.
                ev.set()
            else:
                self._permits += 1
                if self._permits > self.max:
                    self._permits = self.max

    @contextmanager
    def acquire_cm(self, *, wait_timeout: Optional[float] = None):
        p = self.acquire(wait_timeout=wait_timeout)
        try:
            yield p
        finally:
            p.release()

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except Exception:
        return default

# Global gate configured via env
CHATMOCK_MAX_CONCURRENCY = _env_int("CHATMOCK_MAX_CONCURRENCY", 1)
CHATMOCK_QUEUE_LIMIT     = _env_int("CHATMOCK_QUEUE_LIMIT", 100)

# Create rate limiter if RPS > 0
burst = int(CHATMOCK_RATE_LIMIT_RPS * 2) if CHATMOCK_RATE_LIMIT_RPS > 0 else 0
rate_limiter = TokenBucket(CHATMOCK_RATE_LIMIT_RPS, burst) if CHATMOCK_RATE_LIMIT_RPS > 0 else None

gate = Gate(CHATMOCK_MAX_CONCURRENCY, CHATMOCK_QUEUE_LIMIT, rate_limiter)
queue_timeout_seconds = CHATMOCK_QUEUE_TIMEOUT