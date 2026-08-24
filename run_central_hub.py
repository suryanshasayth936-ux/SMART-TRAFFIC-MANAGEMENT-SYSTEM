"""
Smart Traffic Management System — Central Hub Launcher (Mac 2)
Runs the Central Traffic Server & Network Balancing Engine, binding to 0.0.0.0
to receive live telemetry from remote vision nodes on other Macs over LAN/Wi-Fi.
"""

import os
import sys
import time
import socket
import argparse
import webbrowser
import uvicorn


def get_local_ip() -> str:
    """Find the primary local LAN IP address of this Mac."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def main():
    parser = argparse.ArgumentParser(
        description="Smart Traffic Management System — Central Hub Launcher (Run on Mac 2)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the Central Hub server to (default: 8000)"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the web dashboard in the browser"
    )
    args = parser.parse_args()

    local_ip = get_local_ip()
    server_network_url = f"http://{local_ip}:{args.port}"
    server_local_url = f"http://localhost:{args.port}"

    print("\n" + "=" * 78)
    print(" 🚦 SMART TRAFFIC MANAGEMENT SYSTEM — CENTRAL HUB (MAC 2)")
    print("=" * 78)
    print(f"  [1] Central Hub Listening on : 0.0.0.0:{args.port}")
    print(f"  [2] Local Dashboard URL      : {server_local_url}")
    print(f"  [3] Network Access URL       : {server_network_url}")
    print("-" * 78)
    print("  👉 ON MAC 1 (VISION ANALYSIS MAC), RUN:")
    print(f"     python run_vision_node.py --server {server_network_url} --node \"Node A\"")
    print("=" * 78 + "\n")

    # Automatically open Dashboard on Mac 2
    if not args.no_browser:
        try:
            webbrowser.open(server_local_url)
        except Exception:
            pass

    # Start FastAPI server on 0.0.0.0 to accept incoming data from other Macs
    config = uvicorn.Config(
        app="backend.main:app",
        host="0.0.0.0",
        port=args.port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[Central Hub] Shutting down...")


if __name__ == "__main__":
    main()
