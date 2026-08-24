"""
Mock Traffic Feed Generator.
Synthesizes camera frames with road lanes and cars to simulate varying occupancy levels.
"""

import cv2
import numpy as np
import random


def generate_synthetic_traffic_frame(target_occupancy_pct: float = 50.0, width: int = 640, height: int = 480) -> np.ndarray:
    """
    Generate a synthetic road intersection frame with simulated vehicles.
    Vehicles are drawn as rectangles/polygons across lanes to match target occupancy.
    """
    frame = np.full((height, width, 3), (35, 38, 42), dtype=np.uint8)  # Dark asphalt road

    # Draw Road Borders and Markings
    cv2.line(frame, (80, 0), (80, height), (200, 200, 200), 3)
    cv2.line(frame, (width - 80, 0), (width - 80, height), (200, 200, 200), 3)

    # Draw dashed lane dividers
    lane_x1 = width // 3
    lane_x2 = (2 * width) // 3
    for y in range(0, height, 40):
        cv2.line(frame, (lane_x1, y), (lane_x1, y + 20), (255, 255, 255), 2)
        cv2.line(frame, (lane_x2, y), (lane_x2, y + 20), (255, 255, 255), 2)

    # Determine vehicle count to approximate target occupancy
    # A single car is approx 50x90 px ~ 4500 px. Road ROI is roughly (width-160)*height ~ 230,000 px.
    # So 100% occupancy is approx 35-40 vehicles.
    vehicle_count = int(round((target_occupancy_pct / 100.0) * 32))
    
    lanes = [
        (80 + 20, lane_x1 - 20),
        (lane_x1 + 20, lane_x2 - 20),
        (lane_x2 + 20, width - 80 - 20)
    ]

    colors = [
        (220, 50, 50),    # Blue car (BGR)
        (50, 50, 220),    # Red car
        (50, 200, 220),   # Yellow car
        (200, 200, 200),  # Silver car
        (40, 40, 40),     # Dark car
        (50, 180, 50),    # Green truck
    ]

    placed_boxes = []
    attempts = 0
    while len(placed_boxes) < vehicle_count and attempts < 150:
        attempts += 1
        lane = random.choice(lanes)
        car_w = random.randint(35, 55)
        car_h = random.randint(60, 100)
        x = random.randint(lane[0], max(lane[0], lane[1] - car_w))
        y = random.randint(30, height - car_h - 30)

        # Check collision with existing cars
        overlap = False
        for bx, by, bw, bh in placed_boxes:
            if not (x + car_w + 10 < bx or x > bx + bw + 10 or y + car_h + 15 < by or y > by + bh + 15):
                overlap = True
                break

        if not overlap:
            placed_boxes.append((x, y, car_w, car_h))
            car_color = random.choice(colors)
            # Draw car body
            cv2.rectangle(frame, (x, y), (x + car_w, y + car_h), car_color, -1)
            # Draw car windshield / roof
            cv2.rectangle(frame, (x + 4, y + 15), (x + car_w - 4, y + car_h - 20), (20, 20, 20), -1)
            # Draw headlights
            cv2.circle(frame, (x + 6, y + 4), 3, (0, 255, 255), -1)
            cv2.circle(frame, (x + car_w - 6, y + 4), 3, (0, 255, 255), -1)

    return frame
