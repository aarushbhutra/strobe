"""Security tests for API key auth and rate limiting."""
import uuid

import pytest
from fastapi.testclient import TestClient

from api.limiter import limiter
from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestApiKeyAuth:
    def test_auth_disabled_allows_request(self, client, monkeypatch):
        """When API_KEY_ENABLED=false, requests pass without X-Api-Key."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", False)
        monkeypatch.setattr("config.settings.API_KEY", None)

        resp = client.get("/flags")
        assert resp.status_code == 200

    def test_auth_disabled_allows_request_with_any_header(self, client, monkeypatch):
        """Even with a wrong key header, disabled auth allows requests."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", False)
        monkeypatch.setattr("config.settings.API_KEY", None)

        resp = client.get("/flags", headers={"X-Api-Key": "anything"})
        assert resp.status_code == 200

    def test_auth_enabled_missing_key_returns_401(self, client, monkeypatch):
        """When API_KEY_ENABLED=true, missing X-Api-Key header returns 401."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", True)
        monkeypatch.setattr("config.settings.API_KEY", "secret-key")

        resp = client.get("/flags")
        assert resp.status_code == 401

    def test_auth_enabled_wrong_key_returns_401(self, client, monkeypatch):
        """When API_KEY_ENABLED=true, wrong key in X-Api-Key header returns 401."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", True)
        monkeypatch.setattr("config.settings.API_KEY", "correct-secret")

        resp = client.get("/flags", headers={"X-Api-Key": "wrong-secret"})
        assert resp.status_code == 401

    def test_auth_enabled_correct_key_allows_request(self, client, monkeypatch):
        """When API_KEY_ENABLED=true, correct X-Api-Key header allows the request."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", True)
        monkeypatch.setattr("config.settings.API_KEY", "my-secret")

        resp = client.get("/flags", headers={"X-Api-Key": "my-secret"})
        assert resp.status_code == 200

    def test_auth_applies_to_evaluate_endpoints(self, client, monkeypatch):
        """Auth should protect /evaluate endpoints too."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", True)
        monkeypatch.setattr("config.settings.API_KEY", "eval-secret")

        resp = client.post("/evaluate/some-flag", json={"user_id": "u1", "attributes": {}})
        assert resp.status_code == 401

    def test_health_endpoint_is_public(self, client, monkeypatch):
        """Health check should always be accessible without auth."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", True)
        monkeypatch.setattr("config.settings.API_KEY", "secret")

        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root_endpoint_is_public(self, client, monkeypatch):
        """Root endpoint should always be accessible without auth."""
        monkeypatch.setattr("config.settings.API_KEY_ENABLED", True)
        monkeypatch.setattr("config.settings.API_KEY", "secret")

        resp = client.get("/")
        assert resp.status_code == 200


class TestRateLimiting:
    def test_limiter_disabled_allows_repeated_requests(self, client, monkeypatch):
        """When rate limiting is disabled, many requests pass without blocking."""
        monkeypatch.setattr(limiter, "enabled", False)
        limiter.reset()

        for _ in range(15):
            resp = client.get("/flags")
            assert resp.status_code == 200

    def test_limiter_enabled_blocks_excessive_writes(self, client, monkeypatch):
        """When limiter is enabled, exceeding 10 writes/minute returns 429."""
        monkeypatch.setattr(limiter, "enabled", True)
        limiter.reset()

        statuses = []
        for i in range(15):
            unique_key = f"rl-write-{uuid.uuid4().hex[:8]}"
            resp = client.post(
                "/flags",
                json={"key": unique_key, "name": f"Rate Limit Test {i}"},
            )
            statuses.append(resp.status_code)

        assert 429 in statuses, f"Expected 429 after exceeding rate limit, got: {statuses}"

    def test_limiter_enabled_blocks_excessive_reads(self, client, monkeypatch):
        """When limiter is enabled, exceeding 60 reads/minute returns 429."""
        monkeypatch.setattr(limiter, "enabled", True)
        limiter.reset()

        statuses = []
        for _ in range(70):
            resp = client.get("/flags")
            statuses.append(resp.status_code)

        assert 429 in statuses, f"Expected 429 after exceeding rate limit, got: {statuses}"

    def test_limiter_enabled_blocks_excessive_evaluations(self, client, monkeypatch):
        """When limiter is enabled, exceeding 120 evaluations/minute returns 429."""
        monkeypatch.setattr(limiter, "enabled", True)
        limiter.reset()

        statuses = []
        for _ in range(130):
            resp = client.post(
                "/evaluate/nonexistent",
                json={"user_id": "u1", "attributes": {}},
            )
            statuses.append(resp.status_code)

        assert 429 in statuses, f"Expected 429 after exceeding rate limit, got set: {set(statuses)}"
