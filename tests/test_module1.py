"""
Unit tests for Module 1: Area-Occupancy Vision System & FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
import numpy as np

from backend.main import app
from backend.vision.analyzer import calculate_green_light_timer, AreaOccupancyAnalyzer
from backend.vision.mock_feed import generate_synthetic_traffic_frame

client = TestClient(app)


def test_timer_formula_exact_benchmarks():
    """Verify calibrated benchmarks: 80% = 60s, 30% = 20s."""
    assert calculate_green_light_timer(80.0) == 60
    assert calculate_green_light_timer(30.0) == 20


def test_timer_clamping_limits():
    """Verify timers are safely clamped to MIN and MAX thresholds."""
    # 0% occupancy -> should hit MIN_GREEN_TIME (10s)
    assert calculate_green_light_timer(0.0) == 10
    # 100% occupancy -> 0.8 * 100 - 4 = 76s (within max 90s)
    assert 10 <= calculate_green_light_timer(100.0) <= 90


def test_fastapi_calculate_timer_endpoint():
    """Test POST /api/v1/vision/calculate-timer endpoint."""
    response = client.post(
        "/api/v1/vision/calculate-timer",
        json={"occupancy_percentage": 80.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["occupancy_percentage"] == 80.0
    assert data["green_light_seconds"] == 60
    assert data["congestion_level"] == "CRITICAL_CONGESTION"

    response_30 = client.post(
        "/api/v1/vision/calculate-timer",
        json={"occupancy_percentage": 30.0}
    )
    assert response_30.status_code == 200
    data_30 = response_30.json()
    assert data_30["occupancy_percentage"] == 30.0
    assert data_30["green_light_seconds"] == 20
    assert data_30["congestion_level"] == "LOW"


def test_opencv_area_occupancy_analyzer():
    """Test AreaOccupancyAnalyzer on synthetic frame."""
    analyzer = AreaOccupancyAnalyzer()
    frame = generate_synthetic_traffic_frame(target_occupancy_pct=60.0)
    
    occupancy_pct, vehicle_px, total_roi_px, annotated_frame = analyzer.analyze_frame(frame)
    
    assert 0.0 <= occupancy_pct <= 100.0
    assert vehicle_px >= 0
    assert total_roi_px > 0
    assert annotated_frame is not None
    assert annotated_frame.shape == frame.shape

    b64_str = analyzer.encode_frame_to_base64(annotated_frame)
    assert isinstance(b64_str, str)
    assert len(b64_str) > 100


def test_fastapi_synthetic_frame_endpoint():
    """Test GET /api/v1/vision/synthetic-frame endpoint."""
    response = client.get("/api/v1/vision/synthetic-frame?target_occupancy=75.0")
    assert response.status_code == 200
    data = response.json()
    assert "occupancy_percentage" in data
    assert "green_light_seconds" in data
    assert "annotated_image_base64" in data
    assert data["annotated_image_base64"] is not None
