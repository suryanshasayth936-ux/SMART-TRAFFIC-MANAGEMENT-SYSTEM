"""
Split-Screen Simulation Launcher.
Runs FastAPI backend and OpenCV Popup Window with support for custom videos and webcams.
"""

import os
import sys

# Suppress noisy FFmpeg / OpenCV backend decode logs
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

import time
import argparse
import threading
import webbrowser
import uvicorn

from backend.main import app, network_engine
from backend.vision.video_player import VideoSimulationPlayer, generate_heavy_traffic_video


def start_api_server():
    """Start uvicorn server in a separate background thread."""
    config = uvicorn.Config(
        app="backend.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    parser = argparse.ArgumentParser(
        description="Smart Traffic Management System — Split-Screen Simulation Launcher"
    )
    parser.add_argument(
        "--video",
        type=str,
        default="data/heavy_traffic.mp4",
        help="Path to custom video file (e.g. data/my_traffic.mp4 or sample.mov)"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="Camera device index for live webcam feed (e.g. --camera 0)"
    )
    parser.add_argument(
        "--node",
        type=str,
        default="Node A",
        help="Target intersection node ID to feed live data into (default: 'Node A')"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the browser dashboard"
    )
    args = parser.parse_args()

    # Determine video source
    video_source = args.camera if args.camera is not None else args.video

    print("=" * 75)
    print(" 🚦 SMART TRAFFIC MANAGEMENT SYSTEM — SPLIT-SCREEN SIMULATION")
    print("=" * 75)
    print(f"  [1] Target Intersection Node: {args.node}")
    print(f"  [2] Video Source: {'Webcam Index ' + str(args.camera) if args.camera is not None else args.video}")
    print("  [3] Starting FastAPI Server on http://127.0.0.1:8000 ...")
    
    # 1. Start FastAPI server thread
    server_thread = threading.Thread(target=start_api_server, daemon=True)
    server_thread.start()
    time.sleep(1.0)

    # 2. Open Web Dashboard in browser
    dashboard_url = "http://127.0.0.1:8000"
    if not args.no_browser:
        print(f"  [4] Opening Web Dashboard: {dashboard_url}")
        try:
            webbrowser.open(dashboard_url)
        except Exception:
            pass

    # 3. Launch OpenCV Video Window
    print(f"  [5] Launching OpenCV Popup Window: 'AI Vision - Live Area Occupancy'")
    print("      -> Press 'q' or 'ESC' in the popup window to stop.")
    print("=" * 75)

    player = VideoSimulationPlayer(
        video_source=video_source,
        network_engine=network_engine,
        target_node_id=args.node,
        window_title="AI Vision - Live Area Occupancy"
    )

    try:
        player.run_loop()
    except KeyboardInterrupt:
        print("\n[Shutdown] Stopping simulation...")
    finally:
        player.stop()
        print("[Shutdown] Simulation terminated.")


if __name__ == "__main__":
    main()
