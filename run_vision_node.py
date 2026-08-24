"""
Smart Traffic Management System — Vision Edge Node (Run on Mac 2)
"""
import os
import sys

os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

import time
import argparse
import requests
from backend.vision.video_player import VideoSimulationPlayer


def test_server_connection(server_url: str) -> bool:
    endpoint = f"{server_url.rstrip('/')}/api/health"
    try:
        resp = requests.get(endpoint, timeout=2.5)
        return resp.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Smart Traffic Management System — Vision Edge Node")
    parser.add_argument("--server", type=str, default="http://localhost:8000", help="URL of Central Hub on Mac 1")
    parser.add_argument("--node", type=str, default="Node A", help="Target node (default: 'Node A')")
    parser.add_argument("--video", type=str, default="data/heavy_traffic.mp4", help="Path to video")
    parser.add_argument("--camera", type=int, default=None, help="Camera index")
    parser.add_argument("--window-title", type=str, default="AI Vision Node - Live Transmission", help="Window title")
    args = parser.parse_args()

    server_url = args.server.rstrip("/")
    video_source = args.camera if args.camera is not None else args.video

    print("\n" + "=" * 75)
    print(" 👁️ SMART TRAFFIC MANAGEMENT SYSTEM — VISION EDGE NODE")
    print("=" * 75)
    print(f"  [1] Central Hub (Mac 1) : {server_url}")
    print(f"  [2] Target Node         : {args.node}")
    print(f"  [3] Video Feed          : {video_source}")
    print("-" * 75)

    print(f"  Connecting to {server_url} ...", end=" ", flush=True)
    if test_server_connection(server_url):
        print("✅ CONNECTED!")
    else:
        print("⚠️  WAITING / OFFLINE (will retry live)")

    player = VideoSimulationPlayer(
        video_source=video_source,
        server_url=server_url,
        target_node_id=args.node,
        window_title=args.window_title,
    )

    try:
        player.run_loop()
    except KeyboardInterrupt:
        print("\n[Vision Node] Stopped.")
    finally:
        player.stop()


if __name__ == "__main__":
    main()