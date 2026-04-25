import pytest
from fastapi.testclient import TestClient
from main import app
import db.database

client = TestClient(app)

def test_health_check_db_configured():
    response = client.get("/health")
    assert response.status_code == 200
    assert "db" in response.json()
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_lifespan_connects_to_mongo():
    # Verify that the lifespan manages the connection
    assert db.database.client is None
    assert db.database.db is None
    
    # Starting the app using TestClient triggers the lifespan
    with TestClient(app):
        # Now the client and db should be initialized
        assert db.database.client is not None
        assert db.database.db is not None
        
        # Test a quick ping to see if connection is real
        ping_response = await db.database.db.command("ping")
        assert ping_response["ok"] == 1.0

    # After exiting, it should be closed and set to None
    assert db.database.client is None
    assert db.database.db is None
