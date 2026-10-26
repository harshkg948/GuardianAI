import cv2
import numpy as np
import time
import yaml
import os

from src import (
    PrivacyEngine,
    CentroidTracker,
    AWSKMSConnector,
    AgentOrchestrator
)

def main():
    print("=====================================================")
    print("      GuardianAI: Live Video Feed Processing        ")
    print("=====================================================")

    # Load configuration settings
    try:
        with open("config/settings.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Could not load config: {e}")
        return

    # Initialize Core Engine Modules
    privacy_engine = PrivacyEngine(
        blur_kernel=(config['security']['blur_kernel_size'], config['security']['blur_kernel_size'])
    )
    tracker = CentroidTracker(
        max_disappeared=config['tracker']['max_disappeared_frames'],
        loitering_limit=config['tracker']['loitering_threshold_seconds']
    )
    kms = AWSKMSConnector(key_id=config['aws']['kms_key_id'])
    agent = AgentOrchestrator(dwell_threshold=config['tracker']['loitering_threshold_seconds'])

    # Video Source Setup
    video_path = "sample_feed.mp4" 
    
    if os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
        print(f"[INIT] Processing Video File: {video_path}")
    else:
        print(f"[WARNING] {video_path} not found. Falling back to Webcam (0)...")
        cap = cv2.VideoCapture(0)

    # Background Subtractor for Motion/Person Detection (Fail-safe for all OpenCV versions)
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)

    print("[RUN] Processing live frames... Press 'q' in the popup window to stop.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            # Loop video if it ends
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame = cv2.resize(frame, (640, 480))

        # 1. Privacy Anonymization
        anonymized_frame = privacy_engine.anonymize_frame(frame)

        # 2. Motion/Person Bounding Box Extraction via Contours
        fg_mask = bg_subtractor.apply(anonymized_frame)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rects = []
        for contour in contours:
            if cv2.contourArea(contour) > 800:  # Filter out noise
                x, y, w, h = cv2.boundingRect(contour)
                rects.append((x, y, x + w, y + h))

        # 3. Centroid Tracking & Dwell-Time Calculation
        tracked_objects = tracker.update(rects)

        # 4. Agentic Threat Evaluation
        triggers = agent.evaluate_and_act(tracked_objects)

        # Draw overlays on video frame
        for oid, data in tracked_objects.items():
            cx, cy = data["centroid"]
            dwell = data["dwell_time"]

            # Draw Centroid and Tracking ID
            cv2.circle(anonymized_frame, (cx, cy), 5, (0, 255, 255), -1)
            cv2.putText(
                anonymized_frame, f"ID #{oid} [{dwell:.1f}s]", (cx - 20, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2
            )

            # Highlight Loitering Threat Target
            if dwell > config['tracker']['loitering_threshold_seconds']:
                cv2.putText(
                    anonymized_frame, "ALERT: LOITERING DETECTED", (cx - 50, cy - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2
                )

        # Show Live Stream Output Window
        cv2.imshow("GuardianAI Live Video Pipeline", anonymized_frame)

        # Exit on 'q' key press
        if cv2.waitKey(30) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[EXIT] Video Stream Stopped.")

if __name__ == "__main__":
    main()