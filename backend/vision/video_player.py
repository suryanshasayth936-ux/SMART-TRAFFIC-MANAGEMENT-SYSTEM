"""
OpenCV Video Player and Popup Window for Live Split-Screen Simulation.
Supports custom video files (MP4, MOV, AVI), live webcams (0, 1), and RTSP/HTTP streams.
"""

import os
import sys

# Suppress noisy FFmpeg / OpenCV backend decode logs
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

import time
import threading
from typing import Optional, Union
import cv2
import numpy as np

from backend.vision.analyzer import AreaOccupancyAnalyzer, calculate_green_light_timer
from backend.network.graph_engine import TrafficNetworkEngine


def generate_heavy_traffic_video(output_path: str = "data/heavy_traffic.mp4", duration_sec: int = 16, fps: int = 25) -> str:
    """
    Generate a synthetic multi-lane traffic video demonstrating dynamic congestion surges.
    Features moving vehicles oscillating between low traffic (35%) and heavy congestion (84%).
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    width, height = 640, 480
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_sec * fps
    lanes_x = [150, 270, 390, 510]

    # Vehicle fleet state
    vehicles = []
    colors = [
        (220, 60, 60),    # Blue (BGR)
        (60, 60, 220),    # Red
        (60, 200, 220),   # Yellow
        (210, 210, 210),  # White
        (50, 50, 50),     # Dark grey
        (60, 180, 60),    # Green truck
    ]

    for i in range(26):
        vehicles.append({
            'lane': i % 3,
            'y': float(np.random.randint(-400, height + 400)),
            'speed': float(np.random.uniform(2.5, 5.0)),
            'w': int(np.random.randint(42, 52)),
            'h': int(np.random.randint(65, 110)),
            'color': colors[i % len(colors)],
        })

    for frame_idx in range(total_frames):
        phase = (frame_idx / total_frames) * 2 * np.pi
        target_active_count = int(10 + 14 * (0.5 + 0.5 * np.sin(phase - np.pi/2)))

        frame = np.full((height, width, 3), (35, 38, 42), dtype=np.uint8)

        # Road borders
        cv2.line(frame, (90, 0), (90, height), (220, 220, 220), 4)
        cv2.line(frame, (width - 90, 0), (width - 90, height), (220, 220, 220), 4)

        # Dashed lane dividers
        for lane_idx in range(1, 3):
            lx = 90 + lane_idx * ((width - 180) // 3)
            offset_y = (frame_idx * 4) % 40
            for y in range(-40 + offset_y, height, 40):
                cv2.line(frame, (lx, y), (lx, y + 20), (255, 255, 255), 2)

        # Update and draw vehicles
        for v_idx, v in enumerate(vehicles):
            if v_idx < target_active_count:
                v['y'] += v['speed']
                if v['y'] > height + 100:
                    v['y'] = -120
                    v['speed'] = float(np.random.uniform(2.5, 4.5))

                lane_center = 90 + v['lane'] * ((width - 180) // 3) + ((width - 180) // 6)
                vx = int(lane_center - v['w'] // 2)
                vy = int(v['y'])

                if -100 <= vy <= height + 50:
                    cv2.rectangle(frame, (vx, vy), (vx + v['w'], vy + v['h']), v['color'], -1)
                    cv2.rectangle(frame, (vx, vy), (vx + v['w'], vy + v['h']), (20, 20, 20), 2)
                    cv2.rectangle(frame, (vx + 4, vy + 12), (vx + v['w'] - 4, vy + v['h'] - 15), (25, 25, 25), -1)
                    cv2.circle(frame, (vx + 8, vy + 6), 3, (0, 255, 255), -1)
                    cv2.circle(frame, (vx + v['w'] - 8, vy + 6), 3, (0, 255, 255), -1)

        out.write(frame)

    out.release()
    return output_path


import requests
import queue
import base64


class VideoSimulationPlayer:
    """
    Manages continuous video playback / live camera feed, OpenCV popup window rendering,
    and automatic state synchronization with the Network Engine (local in-memory or remote HTTP).
    Supports headless execution in cloud environments (Render/Heroku/Docker).
    """

    def __init__(
        self,
        video_source: Union[str, int] = "data/heavy_traffic.mp4",
        video_path: Optional[str] = None,
        network_engine: Optional[TrafficNetworkEngine] = None,
        server_url: Optional[str] = None,
        target_node_id: str = "Node A",
        window_title: str = "AI Vision - Live Area Occupancy",
        headless: bool = False
    ):
        self.video_source = video_path if video_path is not None else video_source
        self.network_engine = network_engine
        self.server_url = server_url.rstrip("/") if server_url else None
        self.target_node_id = target_node_id
        self.window_title = window_title
        self.headless = headless or os.environ.get("HEADLESS", "false").lower() in ("true", "1")
        self.analyzer = AreaOccupancyAnalyzer()
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        
        # Async HTTP telemetry sender queue for smooth video playback
        self._telemetry_queue: queue.Queue = queue.Queue(maxsize=10)
        self._sender_thread: Optional[threading.Thread] = None

    def _resolve_source(self) -> Union[str, int]:
        """Convert string numbers to int for webcams, or verify file path."""
        if isinstance(self.video_source, str):
            if self.video_source.isdigit():
                return int(self.video_source)
            if not os.path.exists(self.video_source) and not self.video_source.startswith(("http", "rtsp")):
                print(f"[Vision Player] Video '{self.video_source}' not found. Generating default traffic video...")
                generate_heavy_traffic_video(self.video_source)
        return self.video_source

    def _telemetry_sender_worker(self) -> None:
        """Worker thread that transmits occupancy data to the remote server asynchronously."""
        while self.is_running:
            try:
                item = self._telemetry_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                break

            node_id, occupancy_pct, frame_b64 = item
            if self.server_url:
                endpoint = f"{self.server_url}/api/v1/network/update-node"
                try:
                    payload = {
                        "node_id": node_id,
                        "occupancy_percentage": occupancy_pct,
                    }
                    if frame_b64:
                        payload["latest_frame_b64"] = frame_b64

                    requests.post(endpoint, json=payload, timeout=1.0)
                except Exception:
                    pass

    def run_loop(self) -> None:
        """
        Main video loop: reads frames, calculates area occupancy, draws masks,
        updates network engine (locally or remotely), and renders cv2.imshow popup window if not headless.
        """
        source = self._resolve_source()
        is_live_camera = isinstance(source, int)

        print(f"[Vision Player] Opening video source: {source}")
        if self.server_url:
            print(f"[Vision Player] 📡 Remote Server Target: {self.server_url} (Node: {self.target_node_id})")
        if self.headless:
            print("[Vision Player] ☁️ Running in Headless Cloud Mode (GUI display disabled).")
        
        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            print(f"[Vision Player ERROR] Could not open video source '{source}'.")
            return

        self.is_running = True
        
        # Start async sender thread if streaming remotely
        if self.server_url:
            self._sender_thread = threading.Thread(target=self._telemetry_sender_worker, daemon=True)
            self._sender_thread.start()

        if not self.headless:
            print(f"[Vision Player] Window active: '{self.window_title}'")
            print("                -> Press 'q' or 'ESC' on the popup window to stop.")
        
        frame_counter = 0

        try:
            while self.is_running:
                ret, frame = cap.read()
                
                # If reading a video file and reached end, loop seamlessly
                if not ret or frame is None:
                    if not is_live_camera:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                    if not ret or frame is None:
                        break

                frame_counter += 1

                # Resize if frame is excessively large for fast processing
                if frame.shape[1] > 800:
                    scale = 800 / frame.shape[1]
                    frame = cv2.resize(frame, (800, int(frame.shape[0] * scale)))

                # 1. Analyze Area Occupancy
                occupancy_pct, vehicle_px, total_roi_px, annotated_frame = self.analyzer.analyze_frame(
                    frame, use_bg_subtraction=False
                )

                # 2. Synchronize with Network Engine every 4 frames
                if frame_counter % 4 == 0:
                    # Encode frame base64 JPEG thumbnail for live Web UI
                    frame_b64 = None
                    try:
                        thumb = cv2.resize(annotated_frame, (480, int(annotated_frame.shape[0] * 480 / annotated_frame.shape[1])))
                        _, buf = cv2.imencode('.jpg', thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                        frame_b64 = base64.b64encode(buf).decode('utf-8')
                    except Exception:
                        pass

                    # In-memory local engine sync
                    if self.network_engine:
                        self.network_engine.update_node_occupancy(self.target_node_id, occupancy_pct, latest_frame_b64=frame_b64)
                    
                    # Remote HTTP server sync
                    if self.server_url:
                        try:
                            if self._telemetry_queue.full():
                                try:
                                    self._telemetry_queue.get_nowait()
                                except queue.Empty:
                                    pass
                            self._telemetry_queue.put_nowait((self.target_node_id, occupancy_pct, frame_b64))
                        except queue.Full:
                            pass

                # 3. Add Split-Screen Header Watermark
                cv2.rectangle(annotated_frame, (0, 0), (annotated_frame.shape[1], 48), (15, 18, 24), -1)
                src_label = f"CAMERA {source}" if is_live_camera else f"FEED: {self.target_node_id}"
                net_label = f"STREAMING TO -> {self.server_url}" if self.server_url else ("CLOUD STREAM" if self.headless else "STANDALONE LOCAL")
                
                cv2.putText(
                    annotated_frame,
                    f"AI VISION NODE | {src_label} | {occupancy_pct:.1f}% OCCUPANCY",
                    (15, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 255),
                    2
                )
                cv2.putText(
                    annotated_frame,
                    f"TARGET: {self.target_node_id} | {net_label}",
                    (15, 42),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (160, 200, 255),
                    1
                )

                # 4. Display Physical Popup Window if not headless
                if not self.headless:
                    try:
                        cv2.imshow(self.window_title, annotated_frame)
                        key = cv2.waitKey(25) & 0xFF
                        if key == ord('q') or key == 27:
                            print("[Vision Player] Closed by user.")
                            break
                    except Exception:
                        # Auto fallback to headless if cv2.imshow fails in non-GUI environment
                        self.headless = True
                        time.sleep(0.04)
                else:
                    # Maintain smooth 25 FPS frame pacing in headless cloud mode
                    time.sleep(0.04)

        finally:
            cap.release()
            if not self.headless:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
            self.is_running = False
            if self.server_url:
                try:
                    self._telemetry_queue.put_nowait(None)
                except Exception:
                    pass
            print("[Vision Player] Video feed terminated.")

    def start_background(self) -> threading.Thread:
        """Launch video player in a background thread."""
        self._thread = threading.Thread(target=self.run_loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Stop video loop and close windows."""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)