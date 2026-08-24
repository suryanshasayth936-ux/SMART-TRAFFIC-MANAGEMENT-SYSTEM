"""
Pydantic schemas for data validation across all modules.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# --- Module 1: Vision Schemas ---
class OccupancyCalculationRequest(BaseModel):
    occupancy_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Road area occupancy percentage (0 - 100%)",
        examples=[80.0]
    )


class TimerCalculationResponse(BaseModel):
    occupancy_percentage: float
    green_light_seconds: int
    congestion_level: str
    status_message: str


class FrameAnalysisResponse(BaseModel):
    occupancy_percentage: float
    green_light_seconds: int
    vehicle_pixels: int
    total_roi_pixels: int
    congestion_level: str
    annotated_image_base64: Optional[str] = None
    status_message: str


# --- Module 2: Network Balancing Schemas ---
class NodeStatus(BaseModel):
    node_id: str
    name: str
    occupancy_percentage: float
    base_timer: int
    current_timer: int
    is_boosted: bool = False
    boost_reason: Optional[str] = None
    is_emergency: bool = False
    current_signal: str = "GREEN"  # GREEN, YELLOW, RED


class NodeOccupancyUpdateRequest(BaseModel):
    node_id: str = Field(..., description="Intersection Node ID (e.g., 'Node A', 'Node B', 'Node C')")
    occupancy_percentage: float = Field(..., ge=0.0, le=100.0)


class NetworkStatusResponse(BaseModel):
    nodes: Dict[str, NodeStatus]
    topology: List[Dict[str, str]]
    recent_events: List[str]


# --- Module 3: Emergency Override Schemas ---
class EmergencyOverrideRequest(BaseModel):
    ambulance_id: str = Field(..., description="Unique vehicle/ambulance identifier", examples=["AMB-108"])
    target_node: str = Field(..., description="Target intersection node ID (e.g., 'Node A')", examples=["Node A"])
    gps_coordinates: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional GPS lat/lng coordinates",
        examples=[{"lat": 28.6139, "lng": 77.2090}]
    )


class EmergencyOverrideResponse(BaseModel):
    status: str
    ambulance_id: str
    target_node: str
    forced_green_seconds: int
    cleared_corridor_nodes: List[str]
    message: str
