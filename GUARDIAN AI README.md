# GuardianAI: Privacy-First Smart Edge Surveillance & Active Protection System

GuardianAI is a lightweight, privacy-preserving edge surveillance system designed to detect loitering and potential security threats in high-security zones (such as ATM vaults, bank lobbies, or server rooms).

Instead of streaming unencrypted raw video to the cloud, GuardianAI processes frames locally at the edge. It automatically anonymizes sensitive personal data (faces and identifiable ROI), tracks human entities using centroid analysis, evaluates loitering behavior in real-time, and securely transmits encrypted metadata to cloud endpoints using AWS KMS.

---

## Key Features

- **Live Anonymization (Privacy Engine):** Automatically masks faces and sensitive regions in real-time to comply with privacy laws (GDPR/Data Protection).
- **Centroid & Dwell-Time Tracking:** Tracks individuals frame-by-frame and calculates their exact duration in restricted security zones.
- **Agentic Threat Decision Engine:** Triggers immediate local alerts (ROI lock, browser voice warnings, and alert banners) when loitering thresholds are breached.
- **AWS KMS Telemetry Encryption:** Encrypts non-visual metadata with AES-256 envelope encryption before transmission.
- **Natural Web UI Dashboard:** A lightweight Flask-based web interface showing live processed video side-by-side with real-time target analytics and encrypted payloads.
- **Audit Logging:** Exports tamper-evident CSV logs for compliance and incident analysis.

---

## System Architecture

1. **Input Source:** Ingests live CCTV camera feeds or recorded MP4 video files.
2. **Edge Privacy & Tracking Engine:** Applies Gaussian face blurring and assigns spatial centroids with dwell timers.
3. **Agentic Threat Orchestrator:** Evaluates loitering limits and executes multi-channel actions (UI alerts, audio prompts, log entries).
4. **AWS KMS Connector:** Encrypts structured telemetry payload for secure cloud storage.

---

## Directory Structure

```text
GuardianAI/
├── config/
│   └── settings.yaml          # System thresholds & AWS config
├── src/
│   ├── __init__.py
│   ├── privacy_engine.py      # Frame anonymization logic
│   ├── edge_tracker.py       # Centroid & dwell-time tracker
│   ├── aws_kms_connector.py  # AWS KMS telemetry packager
│   └── agent_orchestrator.py # Threat evaluation logic
├── exports/
│   └── audit_telemetry.csv   # Automatically generated audit logs
├── sample_feed.mp4           # Test CCTV video feed
├── app.py                    # Main Flask web app & streaming server
├── main.py                   # Standalone CLI processing script
└── requirements.txt          # Python dependencies
```

---

## Getting Started

### 1. Prerequisites
Ensure Python 3.9+ is installed on your system.

### 2. Installation
Clone or extract the repository and install dependencies:

```powershell
pip install -r requirements.txt
```

*Required packages: `opencv-python`, `flask`, `pyyaml`, `numpy`.*

### 3. Running the Web Console
Place your test video named `sample_feed.mp4` in the project root directory (or connect a webcam) and run:

```powershell
python app.py
```

Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## Configuration

System parameters can be adjusted in `config/settings.yaml`:

- `loitering_threshold_seconds`: Time limit (in seconds) before triggering a loitering breach.
- `blur_kernel_size`: Intensity of privacy masking blur.
- `device_id`: Unique identifier for the edge camera node.