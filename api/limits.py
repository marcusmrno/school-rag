import threading
import time
from collections import deque

from fastapi import Request


class RateLimiter:
    # ponytail: in-memory, one process, resets on restart, and keys are never evicted (memory grows
    # with distinct IPs); a shared store with expiry (Redis) if instances > 1 or traffic grows.
    def __init__(self, limits: list[tuple[int, float]], clock=time.monotonic):
        self.limits = limits
        self.clock = clock
        self.hits: dict[str, deque[float]] = {}
        self.lock = threading.Lock()  # FastAPI runs sync endpoints on a thread pool

    def allow(self, key: str) -> bool:
        with self.lock:
            return self._allow(key)

    def _allow(self, key: str) -> bool:
        now = self.clock()
        q = self.hits.setdefault(key, deque())
        longest = max(window for _, window in self.limits)
        while q and q[0] <= now - longest:
            q.popleft()
        if any(sum(t > now - window for t in q) >= n for n, window in self.limits):
            return False
        q.append(now)
        return True


def client_ip(request: Request) -> str:
    # ponytail: X-Forwarded-For is client-supplied unless a proxy overwrites it, so spoofing dodges
    # the per-IP limits; the daily spend cap still bounds cost.
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def spent_today(conn) -> float:
    row = conn.execute("SELECT usd FROM spend WHERE day = (now() AT TIME ZONE 'utc')::date").fetchone()
    return float(row[0]) if row else 0.0


def add_spend(conn, usd: float) -> None:
    conn.execute(
        "INSERT INTO spend (day, usd) VALUES ((now() AT TIME ZONE 'utc')::date, %s) "
        "ON CONFLICT (day) DO UPDATE SET usd = spend.usd + EXCLUDED.usd",
        (usd,),
    )
