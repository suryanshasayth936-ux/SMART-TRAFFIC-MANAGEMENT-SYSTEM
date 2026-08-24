# Smart Traffic Management System 🚦

A real-time, AI-powered Smart Traffic Management System built with **Python (FastAPI, OpenCV, NetworkX)** and a **Vanilla HTML/CSS/JavaScript Traffic Police Dashboard**.

---

## 🌟 Core Modules

### 1. Area-Occupancy Vision System (OpenCV & FastAPI)
- Measures total road surface area covered by vehicle mass instead of simplistic bounding-box counting.
- Uses OpenCV Region of Interest (ROI) polygon segmentation, edge contrast, and morphological closing to calculate:
  $$\text{Occupancy Percentage} = \left(\frac{\text{Vehicle Pixels in Road ROI}}{\text{Total Road ROI Pixels}}\right) \times 100$$
- Maps area occupancy to calibrated green-light duration ($30\% \to 20\text{s}$, $80\% \to 60\text{s}$, clamped safely between $10\text{s}$ and $90\text{s}$).

### 2. Predictive Network Balancing Engine (NetworkX & Python)
- Models traffic intersections as a directed flow graph ($\text{Node A} \to \text{Node B} \to \text{Node C}$).
- When an upstream node suffers from critical congestion ($> 75\%$ occupancy), the engine automatically increases the downstream intersection's green-light timer by **$+20\%$** to absorb incoming traffic waves.

### 3. Emergency "Green Corridor" Priority Engine (FastAPI)
- Exposes `POST /emergency-override` accepting emergency vehicle ID and target intersection.
- Forces an immediate **90-second Green Wave** across the corridor path to ensure zero-stop passage for ambulances and first responders.

### 4. Traffic Police Command Center Dashboard (HTML5 / Vanilla CSS / Modern JS)
- Modern dark-mode cybernetic dashboard with live telemetry meters for Intersections A, B, and C.
- Interactive traffic surge sliders for real-time demonstration.
- Big Red "EMERGENCY OVERRIDE" button with corridor lock indicators and quick-release toggle.
- Real-time auto-updating event audit stream.
- Interactive OpenCV Vision Lab with test presets and custom image upload.

---

## 🚀 Live Split-Screen Demo Presentation

To run the complete split-screen demo (OpenCV popup window + background FastAPI server + auto-opened web dashboard):

```bash
source .venv/bin/activate
python run_simulation.py
```

- **OpenCV Window:** Pops up with title `"AI Vision - Live Area Occupancy"`, playing `data/heavy_traffic.mp4` with vehicle masks and real-time telemetry HUD.
- **FastAPI Server:** Runs in a background thread on `http://127.0.0.1:8000` with full CORS enabled.
- **Web Dashboard:** Opens in your browser automatically and updates live as the video streams. (You can also double-click `frontend/index.html` directly).
- **Exit:** Press `'q'` or `'ESC'` in the OpenCV window to close the simulation.

---

## 🧪 Running Automated Tests
Run the comprehensive test suite covering all modules:
```bash
source .venv/bin/activate
PYTHONPATH=. pytest -v tests/
```

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET` | Traffic Police Command Center Web Dashboard |
| `/api/health` | `GET` | System health check & active modules list |
| `/api/v1/vision/calculate-timer` | `POST` | Calculates dynamic green timer from occupancy % |
| `/api/v1/vision/analyze-frame` | `POST` | Uploads image frame, executes OpenCV segmentation & returns timer |
| `/api/v1/vision/synthetic-frame` | `GET` | Generates on-demand synthetic road frame with target occupancy |
| `/api/v1/network/status` | `GET` | Live telemetry for Nodes A, B, C & event logs |
| `/api/v1/network/update-node` | `POST` | Updates intersection occupancy and executes predictive wave balancing |
| `/api/v1/network/reset` | `POST` | Resets all intersection timers to baseline |
| `/emergency-override` | `POST` | Forces Emergency Green Wave corridor for emergency vehicles |
| `/emergency-clear` | `POST` | Releases emergency lock and restores dynamic balancing |
| `/api/v1/emergency/active` | `GET` | Lists all active emergency vehicle routes |

---

## 📂 Project Architecture

```text
Project/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application & static dashboard mounting
│   ├── config.py               # Constants, timing parameters & thresholds
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic data validation models
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── analyzer.py         # OpenCV area-occupancy segmentation & timer formula
│   │   ├── mock_feed.py        # Synthetic road traffic frame generator
│   │   └── video_player.py     # Video player & cv2.imshow popup manager
│   ├── network/
│   │   ├── __init__.py
│   │   └── graph_engine.py     # NetworkX directed topology & wave balancing
│   └── emergency/
│       ├── __init__.py
│       └── corridor.py         # Emergency Green Corridor priority preemption
├── frontend/
│   ├── index.html              # Traffic Police Command Center Dashboard
│   ├── css/
│   │   └── styles.css          # Dark cybernetic glassmorphism theme
│   └── js/
│       └── app.js              # Fetch API client with CORS & file:// fallback
├── data/
│   └── heavy_traffic.mp4       # Demo traffic video for split-screen presentation
├── tests/
│   ├── test_module1.py         # Vision & timer formula tests
│   ├── test_module2.py         # Predictive network balancing tests
│   └── test_module3.py         # Emergency Green Corridor tests
├── run_simulation.py           # Single-command Split-Screen Simulation launcher
├── requirements.txt            # Dependency specifications
└── README.md                   # System documentation
```
