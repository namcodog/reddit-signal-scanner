"""
SimpleRateLimiter（app.core.security）单元测试
"""

from app.core.security import SimpleRateLimiter


def test_simple_rate_limiter_allows_within_limit():
    limiter = SimpleRateLimiter()
    key = "unit:test:simple"

    # 允许前3次
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is True
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is True
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is True

    # 第4次超限
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is False

