"""
yolo_processor.py
-----------------
Runs YOLOv8 inference on crowd.mp4 in a background thread.
Stores real-time detection results that Flask endpoints read from.
"""

import threading
import time
import cv2
from collections import deque
from datetime import datetime
from ultralytics import YOLO

# ── shared state (thread-safe via lock) ──────────────────────────────────────
_lock = threading.Lock()

# Stores last 7 per-frame person counts (for density chart)
_density_history = deque(maxlen=7)

# Stores per-second footfall counts (last 8 seconds)
_footfall_history = deque(maxlen=8)

# Stores latest frame's full detection result
_latest_result = {
    "person_count": 0,
    "timestamp": None,
    "status": "starting"   # starting | running | looping | error
}

# Anomaly/alert log (last 50 real alerts from inference)
_real_alerts = deque(maxlen=50)

# ── YOLOv8 background thread ─────────────────────────────────────────────────

def _run_inference(video_path: str, confidence: float = 0.4):
    """
    Continuously processes video file with YOLOv8.
    Loops the video so the dashboard always has live data.
    """
    model = YOLO("yolov8n.pt")   # nano model — fast, good for demo
    PERSON_CLASS = 0              # COCO class 0 = person

    while True:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            with _lock:
                _latest_result["status"] = "error"
            print(f"[YOLOv8] Cannot open video: {video_path}")
            time.sleep(5)
            continue

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frame_interval = 1.0 / fps
        second_counter = 0
        second_counts = []

        with _lock:
            _latest_result["status"] = "running"

        while True:
            ret, frame = cap.read()
            if not ret:
                # Video ended — loop it
                with _lock:
                    _latest_result["status"] = "looping"
                break

            start = time.time()

            # Run inference — only detect persons
            results = model(frame, classes=[PERSON_CLASS],
                            conf=confidence, verbose=False)

            person_count = len(results[0].boxes)
            ts = datetime.now()

            # Update shared state
            with _lock:
                _latest_result["person_count"] = person_count
                _latest_result["timestamp"] = ts.isoformat()
                _latest_result["status"] = "running"
                _density_history.append({
                    "time": ts.strftime("%H:%M:%S"),
                    "count": person_count
                })

            # Accumulate per-second footfall
            second_counts.append(person_count)
            second_counter += 1
            if second_counter >= int(fps):
                avg = sum(second_counts) / len(second_counts)
                with _lock:
                    _footfall_history.append({
                        "time": ts.strftime("%H:%M"),
                        "count": round(avg)
                    })
                second_counts = []
                second_counter = 0

            # Generate real alert if crowd is dense
            if person_count >= 8:
                alert = {
                    "id": f"A-REAL-{int(time.time()*1000)}",
                    "timestamp": ts.isoformat(),
                    "severity": "Critical" if person_count >= 12 else "Warning",
                    "type": "Crowd Density",
                    "camera": "CAM-01: Main Entrance",
                    "details": f"High crowd density detected: {person_count} persons in frame.",
                    "status": "New"
                }
                with _lock:
                    _real_alerts.appendleft(alert)

            # Maintain real-time pace
            elapsed = time.time() - start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()


def start(video_path: str = "crowd.mp4"):
    """Start YOLOv8 inference in a daemon background thread."""
    t = threading.Thread(target=_run_inference, args=(video_path,), daemon=True)
    t.start()
    print(f"[YOLOv8] Inference started on: {video_path}")


# ── public read functions (called by Flask endpoints) ────────────────────────

def get_crowd_density():
    """Returns last 7 real person-count readings for the density chart."""
    with _lock:
        history = list(_density_history)

    if not history:
        # Fallback until first frames are processed
        return {
            "labels": ["--"],
            "data": [0]
        }

    return {
        "labels": [h["time"] for h in history],
        "data":   [h["count"] for h in history]
    }


def get_footfall():
    """Returns per-second average counts for the footfall chart."""
    with _lock:
        history = list(_footfall_history)

    if not history:
        return {"labels": ["--"], "data": [0]}

    return {
        "labels": [h["time"] for h in history],
        "data":   [h["count"] for h in history]
    }


def get_latest_status():
    """Returns the latest frame's person count and inference status."""
    with _lock:
        return dict(_latest_result)


def get_real_alerts():
    """Returns real alerts generated from inference."""
    with _lock:
        return list(_real_alerts)


def get_peak_density():
    """
    Derives peak density per zone from density history.
    Zones are estimated by splitting the frame count proportionally.
    """
    with _lock:
        history = list(_density_history)

    if len(history) < 3:
        return {
            "labels": ["Zone A (Entrance)", "Zone B (Plaza)", "Zone C (Restricted)"],
            "data": [0, 0, 0]
        }

    counts = [h["count"] for h in history]
    third = max(1, len(counts) // 3)
    zone_a = max(counts[:third])
    zone_b = max(counts[third:2*third])
    zone_c = max(counts[2*third:])

    return {
        "labels": ["Zone A (Entrance)", "Zone B (Plaza)", "Zone C (Restricted)"],
        "data": [zone_a, zone_b, zone_c]
    }