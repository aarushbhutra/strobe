"""Shared test configuration. Disables rate limiting globally for all tests."""
import pytest


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    """Disable the rate limiter for all tests so individual tests are not
    constrained by rate limits from previous tests. Rate limit tests
    re-enable it explicitly."""
    from api.limiter import limiter

    monkeypatch.setattr(limiter, "enabled", False)
    limiter.reset()
