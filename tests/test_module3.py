"""
Unit tests for Module 3: Emergency Green Corridor API & Priority Preemption.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app, network_engine, emergency_manager
from backend.config import EMERGENCY_GREEN_TIME

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_network_fixture():
    """Reset network and emergency state before each test."""
    network_engine.reset_network()
    emergency_manager.clear_emergency_override()
    yield


def test_emergency_override_direct_call():
    """Test emergency manager direct trigger."""
    response = emergency_manager.trigger_emergency_override(
        ambulance_id="AMB-108",
        target_node="Node A",
        gps_coordinates={"lat": 28.6139, "lng": 77.2090}
    )
    assert response.status == "EMERGENCY_OVERRIDE_ACTIVE"
    assert response.ambulance_id == "AMB-108"
    assert response.forced_green_seconds == EMERGENCY_GREEN_TIME
    assert "Node A" in response.cleared_corridor_nodes

    nodes = network_engine.get_all_nodes_status()
    assert nodes["Node A"].is_emergency is True
    assert nodes["Node A"].current_timer == EMERGENCY_GREEN_TIME
    assert nodes["Node A"].current_signal == "GREEN"

    # Verify event logged
    assert any("[EMERGENCY OVERRIDE]" in event for event in network_engine.recent_events)


def test_fastapi_emergency_override_endpoint():
    """Test POST /emergency-override endpoint matching exact specification."""
    payload = {
        "ambulance_id": "AMB-999",
        "target_node": "Node B",
        "gps_coordinates": {"lat": 12.9716, "lng": 77.5946}
    }
    response = client.post("/emergency-override", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "EMERGENCY_OVERRIDE_ACTIVE"
    assert data["ambulance_id"] == "AMB-999"
    assert data["target_node"] == "Node B"
    assert data["forced_green_seconds"] == EMERGENCY_GREEN_TIME

    # Check network state
    status_resp = client.get("/api/v1/network/status")
    status_data = status_resp.json()
    assert status_data["nodes"]["Node B"]["is_emergency"] is True
    assert status_data["nodes"]["Node B"]["current_timer"] == EMERGENCY_GREEN_TIME


def test_emergency_clear_endpoint():
    """Test clearing active emergency restore normal operation."""
    # First trigger emergency
    client.post("/emergency-override", json={"ambulance_id": "AMB-123", "target_node": "Node A"})
    
    # Verify emergency active
    active_resp = client.get("/api/v1/emergency/active")
    assert active_resp.json()["count"] == 1

    # Clear emergency
    clear_resp = client.post("/emergency-clear")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "EMERGENCY_CLEARED"

    # Verify cleared
    nodes = network_engine.get_all_nodes_status()
    assert nodes["Node A"].is_emergency is False
    assert nodes["Node A"].current_timer == nodes["Node A"].base_timer


def test_emergency_override_invalid_node():
    """Test 404 response when targeting non-existent node."""
    response = client.post(
        "/emergency-override",
        json={"ambulance_id": "AMB-ERR", "target_node": "Node Z"}
    )
    assert response.status_code == 404
