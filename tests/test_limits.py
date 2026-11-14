from pytest import approx
from starlette.requests import Request

from api.limits import RateLimiter, add_spend, client_ip, spent_today


def req(headers, client):
    return Request(
        {"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()], "client": client}
    )


def test_rate_limiter_blocks_after_limit_and_recovers():
    now = [0.0]
    rl = RateLimiter([(2, 60)], clock=lambda: now[0])
    assert [rl.allow("a"), rl.allow("a"), rl.allow("a")] == [True, True, False]
    assert rl.allow("b")  # per key
    now[0] = 61
    assert rl.allow("a")


def test_rate_limiter_enforces_every_window():
    now = [0.0]
    rl = RateLimiter([(10, 600), (50, 86_400)], clock=lambda: now[0])
    for i in range(50):
        now[0] = i * 700  # spaced past the 10-minute window
        assert rl.allow("a")
    now[0] = 50 * 700
    assert not rl.allow("a")  # daily cap


def test_client_ip_prefers_forwarded_for():
    assert client_ip(req({"x-forwarded-for": "1.2.3.4, 10.0.0.1"}, ("9.9.9.9", 1))) == "1.2.3.4"
    assert client_ip(req({}, ("9.9.9.9", 1))) == "9.9.9.9"


def test_spend_accumulates_per_utc_day(conn):
    add_spend(conn, 0.01)
    add_spend(conn, 0.02)
    assert spent_today(conn) == approx(0.03)
    conn.execute("UPDATE spend SET day = day - 1")
    assert spent_today(conn) == 0.0
