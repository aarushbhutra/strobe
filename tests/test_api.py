import pytest
from fastapi.testclient import TestClient
from main import app
import uuid

# Provide a standard TestClient. TestClient automatically runs lifespan in a background thread.
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_create_and_get_flag(client):
    unique_key = f"test-flag-{uuid.uuid4().hex[:8]}"
    
    # 1. Create flag
    create_payload = {
        "key": unique_key,
        "name": "Test Flag",
        "enabled": True,
        "variants": [
            {"key": "control", "name": "Control", "weight": 50},
            {"key": "treatment", "name": "Treatment", "weight": 50}
        ]
    }
    resp = client.post("/flags", json=create_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"] == unique_key
    assert data["enabled"] is True
    
    # 2. Get flag
    resp = client.get(f"/flags/{unique_key}")
    assert resp.status_code == 200
    assert resp.json()["key"] == unique_key
    
    # 3. List flags
    resp = client.get("/flags")
    assert resp.status_code == 200
    assert any(f["key"] == unique_key for f in resp.json())
    
    # 4. Toggle flag
    resp = client.patch(f"/flags/{unique_key}/toggle")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # 5. Evaluate flag
    eval_payload = {
        "user_id": "user_123",
        "attributes": {}
    }
    resp = client.post(f"/evaluate/{unique_key}", json=eval_payload)
    assert resp.status_code == 200
    eval_data = resp.json()
    # It's disabled now, so reason should be disabled
    assert eval_data["enabled"] is False
    assert eval_data["reason"] == "disabled"
    
    # Toggle back
    client.patch(f"/flags/{unique_key}/toggle")
    
    # Evaluate again
    resp = client.post(f"/evaluate/{unique_key}", json=eval_payload)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["reason"] == "ab_assignment"
    assert resp.json()["variant"] in ["control", "treatment"]

def test_flag_history(client):
    unique_key = f"hist-flag-{uuid.uuid4().hex[:8]}"

    # Create
    client.post("/flags", json={"key": unique_key, "name": "Hist Flag"})
    # Toggle
    client.patch(f"/flags/{unique_key}/toggle")

    # Check history
    resp = client.get(f"/flags/{unique_key}/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 2
    assert history[0]["action"] == "toggled"
    assert history[1]["action"] == "created"


def test_duplicate_flag_key_returns_409(client):
    unique_key = f"dup-flag-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": unique_key, "name": "First"})
    resp = client.post("/flags", json={"key": unique_key, "name": "Second"})
    assert resp.status_code == 409


def test_get_nonexistent_flag_returns_404(client):
    resp = client.get("/flags/does-not-exist-ever")
    assert resp.status_code == 404


def test_toggle_nonexistent_flag_returns_404(client):
    resp = client.patch("/flags/does-not-exist-ever/toggle")
    assert resp.status_code == 404


def test_delete_flag(client):
    unique_key = f"del-flag-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": unique_key, "name": "Delete Me"})

    resp = client.delete(f"/flags/{unique_key}")
    assert resp.status_code == 204

    resp = client.get(f"/flags/{unique_key}")
    assert resp.status_code == 404


def test_delete_nonexistent_flag_returns_404(client):
    resp = client.delete("/flags/does-not-exist-ever")
    assert resp.status_code == 404


def test_update_flag_fields(client):
    unique_key = f"upd-flag-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": unique_key, "name": "Original", "tags": []})

    resp = client.patch(f"/flags/{unique_key}", json={"name": "Updated", "tags": ["beta"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated"
    assert "beta" in data["tags"]


def test_list_flags_enabled_filter(client):
    key_on = f"on-flag-{uuid.uuid4().hex[:8]}"
    key_off = f"off-flag-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": key_on, "name": "On", "enabled": True})
    client.post("/flags", json={"key": key_off, "name": "Off", "enabled": False})

    resp = client.get("/flags?enabled=true")
    assert resp.status_code == 200
    keys = [f["key"] for f in resp.json()]
    assert key_on in keys
    assert key_off not in keys

    resp = client.get("/flags?enabled=false")
    assert resp.status_code == 200
    keys = [f["key"] for f in resp.json()]
    assert key_off in keys
    assert key_on not in keys


def test_evaluate_nonexistent_flag_returns_404(client):
    resp = client.post("/evaluate/does-not-exist-ever", json={"user_id": "u1", "attributes": {}})
    assert resp.status_code == 404


def test_evaluate_disabled_flag(client):
    unique_key = f"eval-dis-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": unique_key, "name": "Disabled", "enabled": False})
    resp = client.post(f"/evaluate/{unique_key}", json={"user_id": "u1", "attributes": {}})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["reason"] == "disabled"


def test_evaluate_simple_boolean_flag(client):
    unique_key = f"bool-flag-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": unique_key, "name": "Bool Flag"})
    resp = client.post(f"/evaluate/{unique_key}", json={"user_id": "u1", "attributes": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["reason"] == "default"
    assert data["variant"] is None


def test_bulk_evaluate(client):
    k1 = f"bulk1-{uuid.uuid4().hex[:8]}"
    k2 = f"bulk2-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": k1, "name": "Bulk 1"})
    client.post("/flags", json={"key": k2, "name": "Bulk 2"})

    resp = client.post("/evaluate/bulk", json={
        "context": {"user_id": "u1", "attributes": {}},
        "flag_keys": [k1, k2]
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert k1 in results
    assert k2 in results


def test_bulk_evaluate_empty_keys_returns_all_enabled(client):
    unique_key = f"bulk-all-{uuid.uuid4().hex[:8]}"
    client.post("/flags", json={"key": unique_key, "name": "All Enabled"})

    resp = client.post("/evaluate/bulk", json={
        "context": {"user_id": "u1", "attributes": {}},
        "flag_keys": []
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert unique_key in results


def test_flag_key_invalid_format_returns_422(client):
    resp = client.post("/flags", json={"key": "-invalid-start", "name": "Bad Key"})
    assert resp.status_code == 422


def test_variant_weights_must_sum_100_returns_400(client):
    resp = client.post("/flags", json={
        "key": f"bad-weights-{uuid.uuid4().hex[:8]}",
        "name": "Bad Weights",
        "variants": [
            {"key": "a", "name": "A", "weight": 30},
            {"key": "b", "name": "B", "weight": 30},
        ]
    })
    assert resp.status_code == 400
