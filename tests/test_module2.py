"""
Unit tests for Module 2: Predictive Network Balancing Engine & REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app, network_engine
from backend.config import HIGH_CONGESTION_THRESHOLD, DOWNSTREAM_BOOST_MULTIPLIER

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_network_fixture():
    """Reset network before each test."""
    network_engine.reset_network()
    yield


def test_network_initial_topology():
    """Verify directed topology A -> B -> C."""
    nodes = network_engine.get_all_nodes_status()
    assert "Node A" in nodes
    assert "Node B" in nodes
    assert "Node C" in nodes

    topology = network_engine.get_topology()
    assert len(topology) == 2
    assert {"from": "Node A", "to": "Node B", "distance": "850m"} in topology
    assert {"from": "Node B", "to": "Node C", "distance": "920m"} in topology


def test_normal_occupancy_no_downstream_boost():
    """Updating Node A to 60% (<= 75%) should NOT boost downstream Node B."""
    result = network_engine.update_node_occupancy("Node A", 60.0)
    nodes = network_engine.get_all_nodes_status()
    
    assert nodes["Node A"].occupancy_percentage == 60.0
    assert nodes["Node B"].is_boosted is False
    assert nodes["Node B"].current_timer == nodes["Node B"].base_timer


def test_high_occupancy_triggers_downstream_boost():
    """Updating Node A to 80% (> 75%) must boost downstream Node B by +20%."""
    # Given Node B's initial base timer
    initial_node_b_base = network_engine.get_node("Node B")["base_timer"]
    expected_boosted_timer = round(initial_node_b_base * DOWNSTREAM_BOOST_MULTIPLIER)

    result = network_engine.update_node_occupancy("Node A", 80.0)
    nodes = network_engine.get_all_nodes_status()

    # Node A assertions
    assert nodes["Node A"].occupancy_percentage == 80.0
    assert nodes["Node A"].current_timer == 60  # 80% -> 60s

    # Node B assertions (downstream)
    assert nodes["Node B"].is_boosted is True
    assert nodes["Node B"].current_timer == expected_boosted_timer
    assert "Predictive wave absorption" in nodes["Node B"].boost_reason

    # Node C assertions (two hops away, unboosted)
    assert nodes["Node C"].is_boosted is False

    # Verify event logged
    matching_events = [e for e in network_engine.recent_events if "Downstream timer adjusted for Node B" in e]
    assert len(matching_events) > 0


def test_traffic_normalization_clears_boost():
    """When Node A returns to <= 75%, downstream boost on Node B is cleared."""
    # First cause congestion on A
    network_engine.update_node_occupancy("Node A", 85.0)
    nodes_congested = network_engine.get_all_nodes_status()
    assert nodes_congested["Node B"].is_boosted is True

    # Then normalize A
    network_engine.update_node_occupancy("Node A", 40.0)
    nodes_normalized = network_engine.get_all_nodes_status()
    assert nodes_normalized["Node B"].is_boosted is False
    assert nodes_normalized["Node B"].current_timer == nodes_normalized["Node B"].base_timer


def test_fastapi_network_status_endpoint():
    """Test GET /api/v1/network/status."""
    response = client.get("/api/v1/network/status")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "topology" in data
    assert "recent_events" in data
    assert "Node A" in data["nodes"]
    assert "Node B" in data["nodes"]
    assert "Node C" in data["nodes"]


def test_fastapi_update_node_endpoint():
    """Test POST /api/v1/network/update-node with high occupancy."""
    response = client.post(
        "/api/v1/network/update-node",
        json={"node_id": "Node A", "occupancy_percentage": 82.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["update_summary"]["occupancy_percentage"] == 82.0
    assert "Node B" in data["update_summary"]["affected_downstream"]

    # Verify state via status endpoint
    status_resp = client.get("/api/v1/network/status")
    status_data = status_resp.json()
    assert status_data["nodes"]["Node B"]["is_boosted"] is True
