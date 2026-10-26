from flask import Flask, render_template_string, Response, jsonify, make_response, send_from_directory
import cv2
import numpy as np
import yaml
import os
import threading
import time
import csv
from datetime import datetime

from src import (
    PrivacyEngine,
    CentroidTracker,
    AWSKMSConnector,
    AgentOrchestrator
)

app = Flask(__name__)

# Load configurations
with open("config/settings.yaml", "r") as f:
    config = yaml.safe_load(f)

privacy_engine = PrivacyEngine(
    blur_kernel=(config['security']['blur_kernel_size'], config['security']['blur_kernel_size'])
)
tracker = CentroidTracker(
    max_disappeared=config['tracker']['max_disappeared_frames'],
    loitering_limit=config['tracker']['loitering_threshold_seconds']
)
kms = AWSKMSConnector(key_id=config['aws']['kms_key_id'])
agent = AgentOrchestrator(dwell_threshold=config['tracker']['loitering_threshold_seconds'])

# Directory setup for alerts and exports
os.makedirs("exports", exist_ok=True)
LOG_FILE = "exports/audit_telemetry.csv"

# Ensure CSV log header exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Device_ID", "Target_ID", "Centroid_X", "Centroid_Y", "Dwell_Time_Sec", "Status"])

# Shared thread-safe state
data_lock = threading.Lock()
latest_telemetry = {
    "tracked_objects": {},
    "kms_payload": "Initializing KMS payload...",
    "system_alert": False
}
current_frame_bytes = None

def video_processing_worker():
    global current_frame_bytes, latest_telemetry
    video_path = "sample_feed.mp4"
    
    if os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
    else:
        cap = cv2.VideoCapture(0)

    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame = cv2.resize(frame, (640, 480))
        h, w, _ = frame.shape

        # Draw Security Zone (Vault Box)
        cv2.rectangle(frame, (50, 50), (w - 50, h - 50), (76, 175, 80), 1)
        cv2.putText(frame, "RESTRICTED SECURITY ZONE A", (60, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (76, 175, 80), 1)

        anonymized_frame = privacy_engine.anonymize_frame(frame)

        fg_mask = bg_subtractor.apply(anonymized_frame)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rects = []
        for contour in contours:
            if cv2.contourArea(contour) > 800:
                x, y, w_box, h_box = cv2.boundingRect(contour)
                rects.append((x, y, x + w_box, y + h_box))

        tracked_objects = tracker.update(rects)
        agent.evaluate_and_act(tracked_objects)

        # AWS KMS Payload Generation
        aws_payload = kms.encrypt_and_pack(config['system']['device_id'], tracked_objects)

        any_loitering = False
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Annotate video frame & Log Data
        for oid, data in tracked_objects.items():
            cx, cy = data["centroid"]
            dwell = data["dwell_time"]
            is_loitering = dwell > config['tracker']['loitering_threshold_seconds']

            if is_loitering:
                any_loitering = True

            cv2.circle(anonymized_frame, (cx, cy), 5, (46, 125, 50), -1)
            cv2.putText(
                anonymized_frame, f"ID #{oid} [{dwell:.1f}s]", (cx - 20, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (46, 125, 50), 2
            )

            if is_loitering:
                cv2.putText(
                    anonymized_frame, "ALERT: LOITERING DETECTED", (cx - 50, cy - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (198, 40, 40), 2
                )

            # Append telemetry to CSV audit log
            try:
                with open(LOG_FILE, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp_str, config['system']['device_id'], oid, cx, cy, round(dwell, 1), "LOITERING" if is_loitering else "NORMAL"])
            except Exception:
                pass

        ret, buffer = cv2.imencode('.jpg', anonymized_frame)
        frame_bytes = buffer.tobytes()

        # Safely update global state
        with data_lock:
            current_frame_bytes = frame_bytes
            latest_telemetry["tracked_objects"] = {
                str(oid): {
                    "centroid": [int(data["centroid"][0]), int(data["centroid"][1])],
                    "dwell_time": round(float(data["dwell_time"]), 1),
                    "is_loitering": bool(data["dwell_time"] > config['tracker']['loitering_threshold_seconds'])
                } for oid, data in tracked_objects.items()
            }
            latest_telemetry["kms_payload"] = str(aws_payload.get("encrypted_payload", ""))
            latest_telemetry["system_alert"] = any_loitering

        time.sleep(0.03)

def generate_stream():
    global current_frame_bytes
    while True:
        with data_lock:
            frame = current_frame_bytes
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03)

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GuardianAI Natural Vision Console</title>
    <style>
        :root {
            --bg-main: #f4f7f4;
            --card-bg: #ffffff;
            --text-dark: #1b2e1e;
            --text-muted: #526355;
            --brand-green: #2e7d32;
            --sage-accent: #e8f5e9;
            --sage-border: #c8e6c9;
            --alert-bg: #ffebee;
            --alert-border: #ef9a9a;
            --alert-text: #c62828;
            --code-bg: #1c2a1e;
            --code-text: #a5d6a7;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: var(--bg-main); color: var(--text-dark); padding: 28px; line-height: 1.5; }
        
        .header { display: flex; justify-content: space-between; align-items: center; background: var(--card-bg); padding: 18px 28px; border-radius: 12px; box-shadow: 0 2px 8px rgba(46, 125, 50, 0.05); margin-bottom: 24px; border: 1px solid var(--sage-border); }
        .header h1 { font-size: 21px; font-weight: 700; color: var(--brand-green); letter-spacing: -0.01em; }
        .header p { font-size: 13px; color: var(--text-muted); margin-top: 2px; }
        
        .header-actions { display: flex; gap: 12px; align-items: center; }
        .badge { background: var(--sage-accent); color: var(--brand-green); font-weight: 600; font-size: 12px; padding: 6px 14px; border-radius: 20px; border: 1px solid var(--sage-border); }
        .btn-export { background: var(--brand-green); color: #ffffff; text-decoration: none; font-size: 12px; font-weight: 600; padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; transition: background 0.2s; }
        .btn-export:hover { background: #1b5e20; }

        .container { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }
        .card { background: var(--card-bg); padding: 22px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); border: 1px solid var(--sage-border); }
        .card-title { font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--brand-green); margin-bottom: 16px; letter-spacing: 0.6px; }
        
        .stream-box { width: 100%; border-radius: 8px; overflow: hidden; background: #0e170f; border: 1px solid var(--sage-border); }
        .stream-box img { width: 100%; display: block; }
        
        .metric-list { display: flex; flex-direction: column; gap: 12px; max-height: 320px; overflow-y: auto; }
        .metric-item { background: var(--sage-accent); border-left: 4px solid var(--brand-green); padding: 12px 14px; border-radius: 0 8px 8px 0; font-size: 13px; border-top: 1px solid var(--sage-border); border-right: 1px solid var(--sage-border); border-bottom: 1px solid var(--sage-border); }
        .metric-item.alert { border-left-color: var(--alert-text); background: var(--alert-bg); border-color: var(--alert-border); }
        
        .code-box { background: var(--code-bg); color: var(--code-text); padding: 14px; border-radius: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; word-break: break-all; max-height: 125px; overflow-y: auto; border: 1px solid #2e4d32; }
    </style>
</head>
<body>

    <div class="header">
        <div>
            <h1>GuardianAI Active Vision Stream</h1>
            <p>Device ID: BANK_ATM_VAULT_CAM_01 | Zone: Vault Security Sector A</p>
        </div>
        <div class="header-actions">
            <a href="/download/logs" class="btn-export">Export Audit Logs (CSV)</a>
            <div class="badge" id="statusBadge">Pipeline Status: LIVE</div>
        </div>
    </div>

    <div class="container">
        <!-- LEFT: Live Video Stream -->
        <div class="card">
            <div class="card-title">Real-Time Edge Video Processing & Zone Overlay</div>
            <div class="stream-box">
                <img src="/video_feed" alt="Live Processing Stream">
            </div>
        </div>

        <!-- RIGHT: Live Natural Analytics -->
        <div style="display: flex; flex-direction: column; gap: 24px;">
            <div class="card">
                <div class="card-title">Live Target Analytics</div>
                <div class="metric-list" id="analyticsList">
                    <div style="font-size: 12px; color: var(--text-muted);">Connecting to edge engine...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">AWS KMS Telemetry Payload</div>
                <div class="code-box" id="kmsPayload">
                    Syncing live KMS telemetry...
                </div>
            </div>
        </div>
    </div>

    <script>
        let lastAlertState = false;

        async function fetchTelemetry() {
            try {
                const response = await fetch('/api/telemetry?t=' + Date.now(), { cache: 'no-store' });
                const data = await response.json();
                
                const analyticsList = document.getElementById('analyticsList');
                const kmsPayload = document.getElementById('kmsPayload');
                const statusBadge = document.getElementById('statusBadge');
                
                if (data.system_alert) {
                    statusBadge.style.background = 'var(--alert-bg)';
                    statusBadge.style.color = 'var(--alert-text)';
                    statusBadge.style.borderColor = 'var(--alert-border)';
                    statusBadge.innerText = 'ALERT: SECURITY BREACH';

                    if (!lastAlertState) {
                        const msg = new SpeechSynthesisUtterance("Warning. Unlawful loitering detected in Security Zone A.");
                        window.speechSynthesis.speak(msg);
                    }
                } else {
                    statusBadge.style.background = 'var(--sage-accent)';
                    statusBadge.style.color = 'var(--brand-green)';
                    statusBadge.style.borderColor = 'var(--sage-border)';
                    statusBadge.innerText = 'Pipeline Status: LIVE';
                }
                lastAlertState = data.system_alert;

                const entries = Object.entries(data.tracked_objects);
                if (entries.length === 0) {
                    analyticsList.innerHTML = '<div style="font-size: 12px; color: var(--text-muted);">No active targets in zone.</div>';
                } else {
                    analyticsList.innerHTML = entries.map(([oid, target]) => {
                        const alertClass = target.is_loitering ? 'alert' : '';
                        const statusText = target.is_loitering 
                            ? '<span style="color: var(--alert-text); font-weight: 600;">LOITERING DETECTED</span><br><span style="color: var(--alert-text); font-size: 11px;">Action: Adaptive Zoom ROI Lock</span>' 
                            : '<span style="color: var(--brand-green); font-size: 11px;">Status: Normal Trajectory</span>';
                        
                        return `
                            <div class="metric-item ${alertClass}">
                                <strong>Target ID #${oid}</strong> [Centroid: ${target.centroid[0]}, ${target.centroid[1]}]<br>
                                Dwell Time: ${target.dwell_time}s<br>
                                ${statusText}
                            </div>
                        `;
                    }).join('');
                }
                
                if (data.kms_payload) {
                    kmsPayload.innerText = data.kms_payload;
                }
            } catch (err) {
                console.error("Telemetry error:", err);
            }
        }

        setInterval(fetchTelemetry, 250);
    </script>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

@app.route('/video_feed')
def video_feed():
    return Response(generate_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/telemetry')
def get_telemetry():
    with data_lock:
        resp = make_response(jsonify(latest_telemetry))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/download/logs')
def download_logs():
    return send_from_directory("exports", "audit_telemetry.csv", as_attachment=True)

if __name__ == '__main__':
    t = threading.Thread(target=video_processing_worker, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=5000, debug=False)