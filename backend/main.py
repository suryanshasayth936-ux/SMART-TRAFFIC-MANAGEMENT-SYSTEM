"""
Smart Traffic Management System - Backend API Entry Point.
Serves REST API endpoints, Traffic Police Web Dashboard, and OpenCV Video Stream.
"""

import os
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import cv2
import numpy as np

from backend.config import (
    MIN_GREEN_TIME,
    MAX_GREEN_TIME,
    HIGH_CONGESTION_THRESHOLD,
)
from backend.models.schemas import (
    OccupancyCalculationRequest,
    TimerCalculationResponse,
    FrameAnalysisResponse,
    NodeOccupancyUpdateRequest,
    NetworkStatusResponse,
    EmergencyOverrideRequest,
    EmergencyOverrideResponse,
)
from backend.vision.analyzer import (
    AreaOccupancyAnalyzer,
    calculate_green_light_timer,
    get_congestion_level,
)
from backend.vision.mock_feed import generate_synthetic_traffic_frame
from backend.network.graph_engine import TrafficNetworkEngine
from backend.emergency.corridor import EmergencyCorridorManager
from backend.vision.video_player import VideoSimulationPlayer

app = FastAPI(
    title="Smart Traffic Management System API",
    description="Vision-Driven Area Occupancy, Predictive Network Balancing, and Emergency Green Corridor System",
    version="1.0.0",
)

# Enable CORS for all origins (allowing double-clicking local index.html directly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Initialize system engines
vision_analyzer = AreaOccupancyAnalyzer()
network_engine = TrafficNetworkEngine()
emergency_manager = EmergencyCorridorManager(network_engine)
video_player = VideoSimulationPlayer(
    video_path=os.path.join(BASE_DIR, "data", "heavy_traffic.mp4"),
    network_engine=network_engine,
    target_node_id="Node A",
)


@app.get("/api/health")
def health_check():
    """System health and operational status check."""
    return {
        "status": "healthy",
        "system": "Smart Traffic Management System",
        "video_player_running": video_player.is_running,
        "active_modules": [
            "Module 1: Area-Occupancy Vision System",
            "Module 2: Predictive Network Balancing Engine",
            "Module 3: Emergency Green Corridor API",
            "Module 4: Traffic Police Web Dashboard",
            "Split-Screen Video Simulation Player"
        ]
    }


# ==========================================
# MODULE 1: Area-Occupancy Vision Endpoints
# ==========================================

@app.post("/api/v1/vision/calculate-timer", response_model=TimerCalculationResponse)
def calculate_timer_from_occupancy(payload: OccupancyCalculationRequest):
    """
    Calculate dynamic green-light duration based on road area occupancy percentage.
    Formula calibrated to: 30% occupancy = 20s, 80% occupancy = 60s.
    """
    occupancy = payload.occupancy_percentage
    timer = calculate_green_light_timer(occupancy)
    congestion = get_congestion_level(occupancy)
    
    return TimerCalculationResponse(
        occupancy_percentage=occupancy,
        green_light_seconds=timer,
        congestion_level=congestion,
        status_message=f"Calculated green signal duration: {timer}s for {occupancy:.1f}% road occupancy ({congestion})."
    )


@app.post("/api/v1/vision/analyze-frame", response_model=FrameAnalysisResponse)
async def analyze_camera_frame(file: UploadFile = File(...)):
    """
    Process an uploaded road camera frame with OpenCV to calculate exact area occupancy %
    and dynamic green-light duration.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image payload could not be decoded.")

    occupancy_pct, vehicle_px, total_roi_px, annotated_frame = vision_analyzer.analyze_frame(frame)
    timer = calculate_green_light_timer(occupancy_pct)
    congestion = get_congestion_level(occupancy_pct)
    annotated_b64 = vision_analyzer.encode_frame_to_base64(annotated_frame)

    return FrameAnalysisResponse(
        occupancy_percentage=occupancy_pct,
        green_light_seconds=timer,
        vehicle_pixels=vehicle_px,
        total_roi_pixels=total_roi_px,
        congestion_level=congestion,
        annotated_image_base64=annotated_b64,
        status_message=f"Vision analysis complete: {occupancy_pct:.1f}% road area occupied ({vehicle_px}/{total_roi_px} px)."
    )


@app.get("/api/v1/vision/synthetic-frame", response_model=FrameAnalysisResponse)
def get_synthetic_traffic_analysis(target_occupancy: float = Query(default=65.0, ge=0.0, le=100.0)):
    """
    Generate and analyze a synthetic traffic scene with the requested occupancy rate.
    Useful for interactive dashboard demonstrations and automated testing.
    """
    frame = generate_synthetic_traffic_frame(target_occupancy_pct=target_occupancy)
    occupancy_pct, vehicle_px, total_roi_px, annotated_frame = vision_analyzer.analyze_frame(frame)
    timer = calculate_green_light_timer(occupancy_pct)
    congestion = get_congestion_level(occupancy_pct)
    annotated_b64 = vision_analyzer.encode_frame_to_base64(annotated_frame)

    return FrameAnalysisResponse(
        occupancy_percentage=occupancy_pct,
        green_light_seconds=timer,
        vehicle_pixels=vehicle_px,
        total_roi_pixels=total_roi_px,
        congestion_level=congestion,
        annotated_image_base64=annotated_b64,
        status_message=f"Synthetic frame analysis: target ~{target_occupancy}%, measured {occupancy_pct:.1f}% -> {timer}s green timer."
    )


# ==================================================
# MODULE 2: Predictive Network Balancing Endpoints
# ==================================================

@app.get("/api/v1/network/status", response_model=NetworkStatusResponse)
def get_network_status():
    """
    Retrieve live state of all nodes (A, B, C), timers, boosts, topology, and recent balancing logs.
    """
    nodes = network_engine.get_all_nodes_status()
    topology = network_engine.get_topology()
    events = network_engine.recent_events
    return NetworkStatusResponse(
        nodes=nodes,
        topology=topology,
        recent_events=events,
    )


@app.post("/api/v1/network/update-node")
def update_node_occupancy(payload: NodeOccupancyUpdateRequest):
    """
    Update area occupancy for a specific intersection.
    If occupancy > 75%, automatically propagates a +20% green timer boost to downstream node(s).
    """
    try:
        result = network_engine.update_node_occupancy(
            node_id=payload.node_id,
            occupancy_pct=payload.occupancy_percentage,
            latest_frame_b64=payload.latest_frame_b64,
        )
        return {
            "status": "success",
            "update_summary": result,
            "network_state": network_engine.get_all_nodes_status(),
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/v1/network/reset")
def reset_network_state():
    """Reset all network nodes and timers to initial default baseline."""
    network_engine.reset_network()
    emergency_manager.clear_emergency_override()
    return {"status": "success", "message": "Network reset to baseline state."}


# ==================================================
# MODULE 3: Emergency "Green Corridor" Endpoints
# ==================================================

@app.post("/emergency-override", response_model=EmergencyOverrideResponse)
@app.post("/api/v1/emergency/override", response_model=EmergencyOverrideResponse)
def trigger_emergency_override(payload: EmergencyOverrideRequest):
    """
    Module 3 Emergency Override endpoint:
    Accepts ambulance ID and target intersection, forces an immediate Green Wave state,
    and returns the updated intersection status.
    """
    try:
        response = emergency_manager.trigger_emergency_override(
            ambulance_id=payload.ambulance_id,
            target_node=payload.target_node,
            gps_coordinates=payload.gps_coordinates,
        )
        return response
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/emergency-clear")
@app.post("/api/v1/emergency/clear")
def clear_emergency_override(ambulance_id: Optional[str] = Query(default=None)):
    """
    Release emergency green wave locks and return network to normal dynamic balancing.
    """
    result = emergency_manager.clear_emergency_override(ambulance_id)
    return result


@app.get("/api/v1/emergency/active")
def get_active_emergencies():
    """Retrieve list of currently active emergency overrides."""
    return {
        "active_emergencies": emergency_manager.active_emergencies,
        "count": len(emergency_manager.active_emergencies)
    }


# ==================================================
# Video Simulation Popup Controls
# ==================================================

@app.post("/api/v1/simulation/start-video-feed")
def start_video_popup_feed():
    """Start background OpenCV video player and popup window."""
    if video_player.is_running:
        return {"status": "already_running", "message": "OpenCV video popup is already active."}
    video_player.start_background()
    return {"status": "started", "message": "OpenCV video popup window launched."}


@app.post("/api/v1/simulation/stop-video-feed")
def stop_video_popup_feed():
    """Stop OpenCV video player and close popup window."""
    video_player.stop()
    return {"status": "stopped", "message": "OpenCV video popup window stopped."}


# ==================================================
# MODULE 4: Static Frontend Serving
# ==================================================

if os.path.exists(os.path.join(FRONTEND_DIR, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")

if os.path.exists(os.path.join(FRONTEND_DIR, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


@app.get("/")
async def serve_dashboard():
    """Serve the Traffic Police Web Dashboard."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        status_code=404,
        content={"error": "Dashboard index.html not found. Please verify frontend directory."}
    )
