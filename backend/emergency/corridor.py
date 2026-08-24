"""
Emergency Green Corridor Engine.
Forces immediate high-priority green wave signals for ambulances and emergency response vehicles.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import networkx as nx

from backend.config import EMERGENCY_GREEN_TIME
from backend.models.schemas import (
    EmergencyOverrideRequest,
    EmergencyOverrideResponse,
    NodeStatus,
)
from backend.network.graph_engine import TrafficNetworkEngine


class EmergencyCorridorManager:
    """
    Coordinates emergency preemption across the traffic network.
    """

    def __init__(self, network_engine: TrafficNetworkEngine):
        self.network_engine = network_engine
        self.active_emergencies: Dict[str, Dict[str, Any]] = {}

    def trigger_emergency_override(
        self,
        ambulance_id: str,
        target_node: str,
        gps_coordinates: Optional[Dict[str, float]] = None,
        clear_entire_downstream_path: bool = True
    ) -> EmergencyOverrideResponse:
        """
        Force a continuous 'Green Wave' state on the target intersection (and its downstream path).
        """
        if target_node not in self.network_engine.graph.nodes:
            raise KeyError(f"Target intersection '{target_node}' not found in network topology.")

        cleared_nodes = [target_node]
        if clear_entire_downstream_path:
            # Include all downstream connected nodes to give the ambulance a clear corridor
            downstream = list(nx.dfs_preorder_nodes(self.network_engine.graph, source=target_node))
            cleared_nodes = downstream

        # Apply Emergency Green Wave to all corridor nodes
        for node_id in cleared_nodes:
            node_data = self.network_engine.graph.nodes[node_id]
            node_data["is_emergency"] = True
            node_data["current_timer"] = EMERGENCY_GREEN_TIME
            node_data["current_signal"] = "GREEN"
            node_data["boost_reason"] = f"EMERGENCY OVERRIDE: Active Green Wave for {ambulance_id}"

        # Track active emergency
        self.active_emergencies[ambulance_id] = {
            "ambulance_id": ambulance_id,
            "target_node": target_node,
            "corridor_nodes": cleared_nodes,
            "gps_coordinates": gps_coordinates,
            "timestamp": datetime.now().isoformat(),
        }

        # Log system event
        corridor_str = " -> ".join(cleared_nodes)
        log_msg = (
            f"[EMERGENCY OVERRIDE] Vehicle '{ambulance_id}' triggered Green Corridor at {target_node}. "
            f"Forced Green Wave (timer: {EMERGENCY_GREEN_TIME}s) along path [{corridor_str}]."
        )
        self.network_engine._log_event(log_msg)

        return EmergencyOverrideResponse(
            status="EMERGENCY_OVERRIDE_ACTIVE",
            ambulance_id=ambulance_id,
            target_node=target_node,
            forced_green_seconds=EMERGENCY_GREEN_TIME,
            cleared_corridor_nodes=cleared_nodes,
            message=f"Emergency Green Wave engaged for {ambulance_id}. Priority signal established for {len(cleared_nodes)} node(s)."
        )

    def clear_emergency_override(self, ambulance_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear active emergency overrides and restore normal dynamic balancing.
        """
        if ambulance_id and ambulance_id in self.active_emergencies:
            emergency = self.active_emergencies.pop(ambulance_id)
            cleared_nodes = emergency["corridor_nodes"]
        else:
            # Clear all active emergencies
            cleared_nodes = list(self.network_engine.graph.nodes)
            self.active_emergencies.clear()

        # Restore cleared nodes to baseline or current occupancy-based timers
        for node_id in cleared_nodes:
            node_data = self.network_engine.graph.nodes[node_id]
            node_data["is_emergency"] = False
            node_data["boost_reason"] = None
            # Update occupancy will recalculate proper base and downstream boost
            self.network_engine.update_node_occupancy(node_id, node_data["occupancy_percentage"])

        log_msg = f"[EMERGENCY CLEARED] Emergency override ended. Network returned to dynamic balancing."
        self.network_engine._log_event(log_msg)

        return {
            "status": "EMERGENCY_CLEARED",
            "message": log_msg,
            "active_emergencies_remaining": len(self.active_emergencies)
        }
