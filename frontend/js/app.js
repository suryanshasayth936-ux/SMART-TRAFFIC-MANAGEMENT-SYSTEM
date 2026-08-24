/**
 * Smart Traffic Command Center - Frontend Logic
 * Connects to FastAPI Backend via Fetch API with CORS & file:// protocol fallback
 */

// Fallback to http://127.0.0.1:8000 if opened directly via file:// in browser
const API_BASE = (window.location.protocol === 'file:' || !window.location.host) 
    ? 'http://127.0.0.1:8000' 
    : window.location.origin;

// State Tracking
let isEmergencyActive = false;
let pollingInterval = null;

// DOM Elements
const apiStatusBadge = document.getElementById('apiStatusBadge');
const corridorStatusBanner = document.getElementById('corridorStatusBanner');
const corridorStatusText = document.getElementById('corridorStatusText');
const emergencyAlertStrip = document.getElementById('emergencyAlertStrip');
const emergencyDetailsText = document.getElementById('emergencyDetailsText');
const eventLogsBody = document.getElementById('eventLogsBody');
const btnEmergencyOverride = document.getElementById('btnEmergencyOverride');
const btnDeactivateEmergency = document.getElementById('btnDeactivateEmergency');
const btnResetNetwork = document.getElementById('btnResetNetwork');

// Initialize on Load
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    fetchNetworkStatus(); // Initial fetch
    startPolling();
    // Load default vision preview
    testSyntheticFrame(80);
});

function initEventListeners() {
    // Emergency Override Trigger
    btnEmergencyOverride.addEventListener('click', handleEmergencyOverride);
    
    // Clear Emergency Trigger
    btnDeactivateEmergency.addEventListener('click', handleClearEmergency);

    // Reset Grid
    btnResetNetwork.addEventListener('click', handleResetNetwork);

    // Interactive Node Density Sliders
    ['Node A', 'Node B', 'Node C'].forEach(nodeId => {
        const slider = document.getElementById(`slider-${nodeId.replace(' ', '-')}`);
        if (slider) {
            slider.addEventListener('change', (e) => {
                const val = parseFloat(e.target.value);
                updateNodeDensity(nodeId, val);
            });
            slider.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value);
                const occVal = document.getElementById(`occVal-${nodeId.replace(' ', '-')}`);
                if (occVal) occVal.innerText = `${val.toFixed(1)}%`;
                const occBar = document.getElementById(`occBar-${nodeId.replace(' ', '-')}`);
                if (occBar) occBar.style.width = `${val}%`;
            });
        }
    });

    // Custom Camera Frame Upload
    const cameraInput = document.getElementById('cameraFileInput');
    if (cameraInput) {
        cameraInput.addEventListener('change', handleCustomFileUpload);
    }
}

/**
 * Start background polling of network status (every 1.5s for fast live sync)
 */
function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(fetchNetworkStatus, 1500);
}

/**
 * Fetch live network status from backend
 */
async function fetchNetworkStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/network/status`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        updateApiStatus(true);
        renderNodes(data.nodes);
        renderLogs(data.recent_events);
        checkEmergencyState(data.nodes);
    } catch (err) {
        console.warn('Network sync offline or connecting...', err.message);
        updateApiStatus(false);
    }
}

function updateApiStatus(isOnline) {
    if (isOnline) {
        apiStatusBadge.className = 'badge online';
        apiStatusBadge.innerText = 'ONLINE (PORT 8000)';
    } else {
        apiStatusBadge.className = 'badge';
        apiStatusBadge.style.background = 'rgba(239, 68, 68, 0.2)';
        apiStatusBadge.style.color = '#ef4444';
        apiStatusBadge.innerText = 'DISCONNECTED (WAITING FOR BACKEND)';
    }
}

/**
 * Render intersection cards for Node A, Node B, Node C
 */
function renderNodes(nodes) {
    for (const [nodeId, nodeData] of Object.entries(nodes)) {
        const idSanitized = nodeId.replace(' ', '-');
        
        const card = document.getElementById(`card-${idSanitized}`);
        const timerEl = document.getElementById(`timer-${idSanitized}`);
        const occVal = document.getElementById(`occVal-${idSanitized}`);
        const occBar = document.getElementById(`occBar-${idSanitized}`);
        const boostBadge = document.getElementById(`boostBadge-${idSanitized}`);
        const slider = document.getElementById(`slider-${idSanitized}`);

        if (!card) continue;

        // Update timer
        if (timerEl) timerEl.innerText = nodeData.current_timer;
        
        // Update occupancy
        if (occVal) occVal.innerText = `${nodeData.occupancy_percentage.toFixed(1)}%`;
        if (occBar) occBar.style.width = `${Math.min(100, Math.max(0, nodeData.occupancy_percentage))}%`;
        if (slider && document.activeElement !== slider) {
            slider.value = nodeData.occupancy_percentage;
        }

        // Signal Light State
        const signalHousing = document.getElementById(`signal-${idSanitized}`);
        if (signalHousing) {
            const lamps = signalHousing.querySelectorAll('.signal-lamp');
            lamps.forEach(lamp => lamp.classList.remove('active'));
            if (nodeData.current_signal === 'RED') {
                signalHousing.querySelector('.signal-lamp.red')?.classList.add('active');
            } else if (nodeData.current_signal === 'YELLOW') {
                signalHousing.querySelector('.signal-lamp.yellow')?.classList.add('active');
            } else {
                signalHousing.querySelector('.signal-lamp.green')?.classList.add('active');
            }
        }

        // Boost & Emergency Badges
        card.classList.remove('boosted', 'emergency-locked');
        boostBadge.className = 'boost-indicator-badge';

        if (nodeData.is_emergency) {
            card.classList.add('emergency-locked');
            boostBadge.classList.add('emergency-active');
            boostBadge.innerHTML = `<span>🚨 FORCED GREEN WAVE (90s)</span>`;
        } else if (nodeData.is_boosted) {
            card.classList.add('boosted');
            boostBadge.classList.add('active-boost');
            boostBadge.innerHTML = `<span>⚡ +20% DOWNSTREAM BOOST (${nodeData.current_timer}s)</span>`;
        } else if (nodeData.occupancy_percentage > 75.0) {
            boostBadge.innerHTML = `<span style="color: #ef4444; font-weight: 700;">🔥 CONGESTED (${nodeData.occupancy_percentage.toFixed(0)}%)</span>`;
        } else {
            boostBadge.innerHTML = `<span>● Baseline Dynamic (${nodeData.base_timer}s)</span>`;
        }
    }
}

/**
 * Render Event Log Table
 */
function renderLogs(events) {
    if (!events || events.length === 0) return;
    
    eventLogsBody.innerHTML = events.slice(0, 15).map(event => {
        let badgeClass = 'badge info';
        let category = 'SYSTEM';

        if (event.includes('[EMERGENCY')) {
            badgeClass = 'badge emergency';
            category = 'EMERGENCY';
        } else if (event.includes('Downstream timer adjusted')) {
            badgeClass = 'badge boost';
            category = 'WAVE BOOST';
        } else if (event.includes('High congestion')) {
            badgeClass = 'badge boost';
            category = 'CONGESTION';
        } else if (event.includes('normalized')) {
            badgeClass = 'badge normal';
            category = 'BALANCED';
        }

        const match = event.match(/^\[(.*?)\]\s*(.*)$/);
        const timestamp = match ? `[${match[1]}]` : '[NOW]';
        const content = match ? match[2] : event;

        return `
            <tr>
                <td class="mono">${timestamp}</td>
                <td><span class="${badgeClass}">${category}</span></td>
                <td>${content}</td>
            </tr>
        `;
    }).join('');
}

/**
 * Check if emergency is active across nodes
 */
function checkEmergencyState(nodes) {
    const hasEmergency = Object.values(nodes).some(n => n.is_emergency);
    isEmergencyActive = hasEmergency;

    if (hasEmergency) {
        corridorStatusBanner.className = 'corridor-banner emergency';
        corridorStatusText.innerText = '🚨 EMERGENCY GREEN CORRIDOR ENGAGED';
        emergencyAlertStrip.classList.remove('hidden');
    } else {
        corridorStatusBanner.className = 'corridor-banner normal';
        corridorStatusText.innerText = 'SYSTEM ACTIVE • DYNAMIC BALANCING MODE';
        emergencyAlertStrip.classList.add('hidden');
    }
}

/**
 * Simulate quick traffic surge
 */
window.simulateSurge = function(nodeId, percentage) {
    updateNodeDensity(nodeId, percentage);
};

/**
 * Update Node Density on Backend
 */
async function updateNodeDensity(nodeId, occupancyPct) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/network/update-node`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: nodeId,
                occupancy_percentage: occupancyPct
            })
        });

        if (!response.ok) throw new Error('Failed to update node occupancy');
        const data = await response.json();
        renderNodes(data.network_state);
        fetchNetworkStatus();
    } catch (err) {
        console.error('Error updating node density:', err);
    }
}

/**
 * Trigger Module 3 Emergency Override
 */
async function handleEmergencyOverride() {
    const ambulanceId = document.getElementById('ambulanceSelect').value;
    const targetNode = document.getElementById('targetNodeSelect').value;

    try {
        btnEmergencyOverride.disabled = true;
        btnEmergencyOverride.style.opacity = '0.7';

        const response = await fetch(`${API_BASE}/emergency-override`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ambulance_id: ambulanceId,
                target_node: targetNode,
                gps_coordinates: { lat: 28.6139, lng: 77.2090 }
            })
        });

        if (!response.ok) throw new Error('Emergency override request failed');
        const result = await response.json();

        emergencyDetailsText.innerText = `Vehicle '${result.ambulance_id}' forced priority Green Wave at ${result.target_node} (Corridor: ${result.cleared_corridor_nodes.join(' → ')})`;
        
        await fetchNetworkStatus();
    } catch (err) {
        alert(`Emergency Override Error: ${err.message}`);
    } finally {
        btnEmergencyOverride.disabled = false;
        btnEmergencyOverride.style.opacity = '1';
    }
}

/**
 * Clear Emergency Override
 */
async function handleClearEmergency() {
    try {
        const response = await fetch(`${API_BASE}/emergency-clear`, { method: 'POST' });
        if (!response.ok) throw new Error('Clear emergency request failed');
        await fetchNetworkStatus();
    } catch (err) {
        console.error('Error clearing emergency:', err);
    }
}

/**
 * Reset Network Grid
 */
async function handleResetNetwork() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/network/reset`, { method: 'POST' });
        if (!response.ok) throw new Error('Reset request failed');
        await fetchNetworkStatus();
    } catch (err) {
        console.error('Error resetting network:', err);
    }
}

/**
 * Module 1 Vision Lab: Test Synthetic Frame Preset
 */
window.testSyntheticFrame = async function(occupancyPct) {
    const statusLabel = document.getElementById('visionStatusLabel');
    const previewImg = document.getElementById('visionPreviewImg');
    const placeholder = document.getElementById('visionPlaceholder');
    const occEl = document.getElementById('visionMetricOcc');
    const timerEl = document.getElementById('visionMetricTimer');
    const pxEl = document.getElementById('visionMetricPx');

    try {
        statusLabel.innerText = 'PROCESSING...';
        statusLabel.className = 'badge';
        statusLabel.style.background = 'rgba(245, 158, 11, 0.2)';
        statusLabel.style.color = '#f59e0b';

        const response = await fetch(`${API_BASE}/api/v1/vision/synthetic-frame?target_occupancy=${occupancyPct}`);
        if (!response.ok) throw new Error('Failed to analyze synthetic frame');
        
        const data = await response.json();

        if (data.annotated_image_base64) {
            previewImg.src = `data:image/jpeg;base64,${data.annotated_image_base64}`;
            previewImg.style.display = 'block';
            if (placeholder) placeholder.style.display = 'none';
        }

        occEl.innerText = `${data.occupancy_percentage.toFixed(1)}%`;
        timerEl.innerText = `${data.green_light_seconds}s (${data.congestion_level})`;
        pxEl.innerText = `${data.vehicle_pixels.toLocaleString()} / ${data.total_roi_pixels.toLocaleString()} px`;

        statusLabel.innerText = 'ANALYSIS COMPLETE';
        statusLabel.className = 'badge ready';
        statusLabel.style.background = 'rgba(16, 185, 129, 0.15)';
        statusLabel.style.color = '#10b981';
    } catch (err) {
        console.error('Vision lab error:', err);
        statusLabel.innerText = 'ERROR';
    }
};

/**
 * Custom File Upload Analysis
 */
async function handleCustomFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    document.getElementById('fileNameLabel').innerText = file.name;
    const statusLabel = document.getElementById('visionStatusLabel');
    const previewImg = document.getElementById('visionPreviewImg');
    const placeholder = document.getElementById('visionPlaceholder');
    const occEl = document.getElementById('visionMetricOcc');
    const timerEl = document.getElementById('visionMetricTimer');
    const pxEl = document.getElementById('visionMetricPx');

    try {
        statusLabel.innerText = 'ANALYZING FRAME...';
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/api/v1/vision/analyze-frame`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Image analysis failed');
        const data = await response.json();

        if (data.annotated_image_base64) {
            previewImg.src = `data:image/jpeg;base64,${data.annotated_image_base64}`;
            previewImg.style.display = 'block';
            if (placeholder) placeholder.style.display = 'none';
        }

        occEl.innerText = `${data.occupancy_percentage.toFixed(1)}%`;
        timerEl.innerText = `${data.green_light_seconds}s (${data.congestion_level})`;
        pxEl.innerText = `${data.vehicle_pixels.toLocaleString()} / ${data.total_roi_pixels.toLocaleString()} px`;

        statusLabel.innerText = 'CUSTOM FRAME ANALYZED';
        statusLabel.className = 'badge ready';
    } catch (err) {
        console.error('Custom file analysis failed:', err);
        alert(`Analysis error: ${err.message}`);
    }
}
