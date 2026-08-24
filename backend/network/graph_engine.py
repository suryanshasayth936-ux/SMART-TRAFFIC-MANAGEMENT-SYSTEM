"""
Predictive Network Balancing Engine using NetworkX.
Maintains directed topology for Intersections A -> B -> C and automatically propagates
downstream green-timer boosts when an upstream node exceeds the congestion threshold (> 75%).
"""

from typing import Dict, List, Any, Optional
import networkx as nx
from datetime import datetime

from backend.config import (
    HIGH_CONGESTION_THRESHOLD,
    DOWNSTREAM_BOOST_MULTIPLIER,
    MAX_GREEN_TIME,
)
from backend.models.schemas import NodeStatus
from backend.vision.analyzer import calculate_green_light_timer


class TrafficNetworkEngine:
    """
    Manages traffic topology graph and predictive corridor balancing.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.recent_events: List[str] = []
        self._initialize_topology()

    def _log_event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.recent_events.insert(0, log_entry)
        # Keep maximum 50 recent events
        if len(self.recent_events) > 50:
            self.recent_events.pop()

    def _initialize_topology(self) -> None:
        """Create the A -> B -> C directed traffic corridor."""
        self.graph.clear()
        self.recent_events.clear()

        # Define 3 connected intersections
        nodes_config = [
            ("Node A", "Intersection A (North Gate / Uptown)", 30.0),
            ("Node B", "Intersection B (Central Hub / Midtown)", 40.0),
            ("Node C", "Intersection C (South Terminal / Downtown)", 35.0),
        ]

        for node_id, name, initial_occ in nodes_config:
            base_timer = calculate_green_light_timer(initial_occ)
            self.graph.add_node(
                node_id,
                name=name,
                occupancy_percentage=initial_occ,
                base_timer=base_timer,
                current_timer=base_timer,
                is_boosted=False,
                boost_reason=None,
                is_emergency=False,
                current_signal="GREEN",
            )

        # Directed arterial flow: Node A -> Node B -> Node C
        self.graph.add_edge("Node A", "Node B", distance_m=850, avg_travel_time_sec=45)
        self.graph.add_edge("Node B", "Node C", distance_m=920, avg_travel_time_sec=50)

        self._log_event("Traffic Network initialized: Topology [Node A -> Node B -> Node C] active.")

    def get_node(self, node_id: str) -> Dict[str, Any]:
        """Fetch raw node attribute dictionary."""
        if node_id not in self.graph.nodes:
            raise KeyError(f"Intersection '{node_id}' does not exist in network topology.")
        return self.graph.nodes[node_id]

    def get_all_nodes_status(self) -> Dict[str, NodeStatus]:
        """Return standardized status models for all intersections."""
        statuses = {}
        for node_id in self.graph.nodes:
            data = self.graph.nodes[node_id]
            statuses[node_id] = NodeStatus(
                node_id=node_id,
                name=data["name"],
                occupancy_percentage=data["occupancy_percentage"],
                base_timer=data["base_timer"],
                current_timer=data["current_timer"],
                is_boosted=data["is_boosted"],
                boost_reason=data.get("boost_reason"),
                is_emergency=data.get("is_emergency", False),
                current_signal=data.get("current_signal", "GREEN"),
            )
        return statuses

    def get_topology(self) -> List[Dict[str, str]]:
        """Return list of directed edges representing traffic flow."""
        return [
            {"from": u, "to": v, "distance": f"{self.graph[u][v].get('distance_m', 0)}m"}
            for u, v in self.graph.edges
        ]

    def update_node_occupancy(self, node_id: str, occupancy_pct: float) -> Dict[str, Any]:
        """
        Update the area occupancy of an intersection and execute predictive network balancing.
        If occupancy > 75%, automatically boost downstream intersection(s) by 20%.
        """
        if node_id not in self.graph.nodes:
            raise KeyError(f"Intersection '{node_id}' not found in topology.")

        node_data = self.graph.nodes[node_id]
        old_occ = node_data["occupancy_percentage"]
        node_data["occupancy_percentage"] = occupancy_pct

        # Recalculate node's own base timer from occupancy
        base_timer = calculate_green_light_timer(occupancy_pct)
        node_data["base_timer"] = base_timer
        
        # If node is not emergency-overridden and not boosted by an upstream node, set current = base
        if not node_data.get("is_emergency", False) and not node_data.get("is_boosted", False):
            node_data["current_timer"] = base_timer

        events_generated: List[str] = []
        downstream_nodes = list(self.graph.successors(node_id))

        # Check for congestion threshold (> 75%)
        if occupancy_pct > HIGH_CONGESTION_THRESHOLD:
            msg = f"High congestion alert on {node_id} ({occupancy_pct:.1f}% > {HIGH_CONGESTION_THRESHOLD}%). Base timer: {base_timer}s."
            self._log_event(msg)
            events_generated.append(msg)

            # Predictive balancing: propagate +20% boost to downstream nodes
            for target_id in downstream_nodes:
                target_data = self.graph.nodes[target_id]
                
                # Skip if already under emergency override
                if target_data.get("is_emergency", False):
                    continue

                downstream_base = target_data["base_timer"]
                boosted_timer = min(MAX_GREEN_TIME, round(downstream_base * DOWNSTREAM_BOOST_MULTIPLIER))
                
                target_data["current_timer"] = boosted_timer
                target_data["is_boosted"] = True
                target_data["boost_reason"] = (
                    f"Predictive wave absorption (+20%) from upstream {node_id} (Congestion: {occupancy_pct:.1f}%)"
                )

                boost_log = (
                    f"Downstream timer adjusted for {target_id}: boosted from {downstream_base}s to "
                    f"{boosted_timer}s (+20%) to absorb incoming wave from {node_id}."
                )
                self._log_event(boost_log)
                events_generated.append(boost_log)
        else:
            # If occupancy returned to normal (<= 75%), check if downstream should be unboosted
            if old_occ > HIGH_CONGESTION_THRESHOLD:
                normalize_msg = f"Traffic normalized on {node_id} ({occupancy_pct:.1f}% <= {HIGH_CONGESTION_THRESHOLD}%)."
                self._log_event(normalize_msg)
                events_generated.append(normalize_msg)

                for target_id in downstream_nodes:
                    target_data = self.graph.nodes[target_id]
                    # Check if any OTHER upstream node is still congesting this target
                    other_congested_predecessors = [
                        pred for pred in self.graph.predecessors(target_id)
                        if pred != node_id and self.graph.nodes[pred]["occupancy_percentage"] > HIGH_CONGESTION_THRESHOLD
                    ]
                    
                    if not other_congested_predecessors and not target_data.get("is_emergency", False):
                        target_data["is_boosted"] = False
                        target_data["boost_reason"] = None
                        target_data["current_timer"] = target_data["base_timer"]
                        
                        reset_log = f"Downstream timer normalized for {target_id} back to {target_data['base_timer']}s."
                        self._log_event(reset_log)
                        events_generated.append(reset_log)

        return {
            "node_id": node_id,
            "occupancy_percentage": occupancy_pct,
            "base_timer": node_data["base_timer"],
            "current_timer": node_data["current_timer"],
            "affected_downstream": downstream_nodes,
            "events": events_generated,
        }

    def reset_network(self) -> None:
        """Reset entire network to initial state."""
        self._initialize_topology()
