"""
Area-Occupancy Vision System (OpenCV).
Calculates the total percentage of road surface area covered by vehicles and maps it to dynamic green-light timers.
"""

import base64
from typing import Optional, Tuple, List
import cv2
import numpy as np

from backend.config import (
    MIN_GREEN_TIME,
    MAX_GREEN_TIME,
    TIMER_SLOPE,
    TIMER_INTERCEPT,
    DEFAULT_ROI_NORMALIZED,
)


def calculate_green_light_timer(occupancy_pct: float) -> int:
    """
    Map road area occupancy percentage to a dynamically calculated green-light timer.
    Calibrated formula:
        80% occupancy -> 60 seconds
        30% occupancy -> 20 seconds
    Formula: Timer = round(TIMER_SLOPE * occupancy + TIMER_INTERCEPT)
    Clamped within [MIN_GREEN_TIME, MAX_GREEN_TIME].
    """
    raw_timer = round(TIMER_SLOPE * occupancy_pct + TIMER_INTERCEPT)
    clamped_timer = max(MIN_GREEN_TIME, min(MAX_GREEN_TIME, raw_timer))
    return int(clamped_timer)


def get_congestion_level(occupancy_pct: float) -> str:
    """Classify traffic level based on occupancy percentage."""
    if occupancy_pct < 40.0:
        return "LOW"
    elif occupancy_pct <= 75.0:
        return "MODERATE"
    else:
        return "CRITICAL_CONGESTION"


class AreaOccupancyAnalyzer:
    """
    OpenCV-based road area occupancy detector.
    Analyzes camera frames using morphological masking and ROI area segmentation.
    """

    def __init__(self):
        # MOG2 background subtractor for continuous video stream processing
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=25, detectShadows=True
        )

    def _create_roi_mask(
        self,
        height: int,
        width: int,
        roi_polygon: Optional[List[Tuple[int, int]]] = None
    ) -> np.ndarray:
        """Create a binary mask representing the designated road surface area."""
        mask = np.zeros((height, width), dtype=np.uint8)
        if roi_polygon is None or len(roi_polygon) < 3:
            # Default normalized road polygon
            pts = np.array(
                [[int(x * width), int(y * height)] for x, y in DEFAULT_ROI_NORMALIZED],
                dtype=np.int32
            )
        else:
            pts = np.array(roi_polygon, dtype=np.int32)

        cv2.fillPoly(mask, [pts], 255)
        return mask

    def analyze_frame(
        self,
        frame: np.ndarray,
        roi_polygon: Optional[List[Tuple[int, int]]] = None,
        use_bg_subtraction: bool = False
    ) -> Tuple[float, int, int, np.ndarray]:
        """
        Analyze a single image/frame to calculate area occupancy within the road ROI.
        
        Returns:
            Tuple of:
            - occupancy_percentage: float (0.0 to 100.0)
            - vehicle_pixel_count: int
            - total_roi_pixels: int
            - annotated_frame: np.ndarray (OpenCV BGR image with visual overlays)
        """
        height, width = frame.shape[:2]
        roi_mask = self._create_roi_mask(height, width, roi_polygon)
        total_roi_pixels = int(cv2.countNonZero(roi_mask))

        if total_roi_pixels == 0:
            return 0.0, 0, 1, frame

        if use_bg_subtraction:
            # Video stream foreground detection
            fg_mask = self.bg_subtractor.apply(frame)
            # Remove shadows (shadows typically labeled as 127)
            _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        else:
            # Static image vehicle segmentation using adaptive edge and saturation contrast
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Canny edges & Otsu threshold combination
            edges = cv2.Canny(blurred, 50, 150)
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            combined = cv2.bitwise_or(edges, otsu)
            
            # Morphological dilation & closing to solidify vehicle silhouettes
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
            thresh = cv2.dilate(closed, kernel, iterations=1)

        # Restrict detected vehicles strictly inside the Road ROI
        vehicle_in_roi = cv2.bitwise_and(thresh, thresh, mask=roi_mask)
        vehicle_pixel_count = int(cv2.countNonZero(vehicle_in_roi))

        occupancy_pct = round((vehicle_pixel_count / total_roi_pixels) * 100.0, 2)
        occupancy_pct = max(0.0, min(100.0, occupancy_pct))

        # Generate visual overlay for dashboard display
        annotated_frame = frame.copy()
        
        # 1. Overlay road ROI outline in Cyan
        contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(annotated_frame, contours, -1, (255, 200, 0), 2)
        
        # 2. Color vehicle area mask in Red/Orange tint
        vehicle_overlay = annotated_frame.copy()
        vehicle_overlay[vehicle_in_roi > 0] = [0, 69, 255]  # Red-Orange in BGR
        cv2.addWeighted(vehicle_overlay, 0.45, annotated_frame, 0.55, 0, annotated_frame)

        # 3. Add telemetry HUD text onto frame
        calculated_timer = calculate_green_light_timer(occupancy_pct)
        hud_text_1 = f"Road Occupancy: {occupancy_pct:.1f}%"
        hud_text_2 = f"Dynamic Green Timer: {calculated_timer}s"
        
        cv2.putText(annotated_frame, hud_text_1, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(annotated_frame, hud_text_2, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 100), 2)

        return occupancy_pct, vehicle_pixel_count, total_roi_pixels, annotated_frame

    def encode_frame_to_base64(self, frame: np.ndarray) -> str:
        """Encode OpenCV frame to Base64 JPEG string for web transmission."""
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return base64.b64encode(buffer).decode('utf-8')
