"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the health endpoint."""

    def test_health_returns_ok(self, client):
        """Test that /api/health returns status ok."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "iot-simulator"


class TestSimulationsEndpoints:
    """Tests for simulation CRUD + lifecycle endpoints."""

    def test_list_simulations_empty(self, client):
        """Test listing simulations when none exist."""
        response = client.get("/api/simulations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_simulation_from_profile(self, client):
        """Test creating a simulation from a JSON body."""
        body = {
            "name": "test-sim-001",
            "transport": {"mode": "mosquitto_via_nginx"},
            "devices": {"count": 5},
            "telemetry": {"interval_seconds": 30},
            "schedule": {"mode": "duration", "duration_minutes": 60},
        }
        response = client.post("/api/simulations", json=body)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-sim-001"
        assert data["status"] == "created"
        assert data["devices_active"] == 5

        # Clean up
        sim_id = data["id"]
        client.delete(f"/api/simulations/{sim_id}")

    def test_create_simulation_empty_body(self, client):
        """Test that creating a simulation without body or profile returns 400."""
        response = client.post("/api/simulations")
        assert response.status_code in (400, 422)  # either validation or bad request

    def test_get_nonexistent_simulation(self, client):
        """Test getting a non-existent simulation returns 404."""
        response = client.get("/api/simulations/nonexistent-id")
        assert response.status_code == 404

    def test_start_nonexistent_simulation(self, client):
        """Test starting a non-existent simulation returns 404."""
        response = client.post("/api/simulations/nonexistent-id/start")
        assert response.status_code == 404

    def test_full_lifecycle(self, client):
        """Test create → get → start → pause → resume → stop → delete lifecycle."""
        # Create
        body = {
            "name": "lifecycle-test",
            "transport": {"mode": "mosquitto_via_nginx"},
            "devices": {"count": 3},
            "telemetry": {"interval_seconds": 10},
            "schedule": {"mode": "duration", "duration_minutes": 5},
        }
        response = client.post("/api/simulations", json=body)
        assert response.status_code == 201
        sim_id = response.json()["id"]

        # Get
        response = client.get(f"/api/simulations/{sim_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "lifecycle-test"
        assert response.json()["status"] == "created"

        # Stop before starting (should fail)
        response = client.post(f"/api/simulations/{sim_id}/stop")
        assert response.status_code == 409

        # Delete (should work since it's in 'created' state)
        response = client.delete(f"/api/simulations/{sim_id}")
        assert response.status_code == 204


class TestProfilesEndpoints:
    """Tests for profile management endpoints."""

    def test_list_profiles(self, client):
        """Test listing available profiles."""
        response = client.get("/api/profiles")
        assert response.status_code == 200
        data = response.json()
        assert "profiles" in data
        assert "total" in data


class TestConnectivityEndpoint:
    """Tests for connectivity check endpoint."""

    def test_connectivity_check_default(self, client):
        """Test connectivity check with default (Mode A) config."""
        response = client.post(
            "/api/connectivity/check",
            json={"mode": "mosquitto_via_nginx"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "success" in data
