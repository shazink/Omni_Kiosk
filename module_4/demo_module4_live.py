#!/usr/bin/env python3
"""
OmniKiosk - Live Interactive Demo for Module 4
==============================================
Runs real-time camera capture on /dev/video0 using MediaPipe Hands
and displays the live geometric gesture classification.

Supports:
  - Full GUI window with high-contrast HUD overlay (if desktop display available)
  - Seamless CLI console mode with ASCII HUD (if running in headless/remote terminal)

Controls:
  - Show Thumbs-Up to camera (hold for 0.5s to trigger confirmation).
  - Show Open Palm to camera (triggers reset / cancellation).
  - Show Number gestures (1, 2 / V-sign, 3, 4, 5).
  - Press 'q' or ESC (in GUI window) or Ctrl+C (in terminal) to exit.
"""

import os
from pathlib import Path
import sys
import time
import cv2

# Ensure module path is included regardless of working directory
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

from vision_gesture_engine import VisionGestureEngine, MP_AVAILABLE


def main():
    if not MP_AVAILABLE:
        print("[ERROR] MediaPipe is not installed. Please install mediapipe first.")
        sys.exit(1)

    print("=" * 68)
    print(" OmniKiosk - Module 4: Live Vision & Gesture Engine")
    print("=" * 68)
    print("Opening camera /dev/video0...")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[WARNING] Could not open /dev/video0. Trying /dev/video1...")
        cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        print("[ERROR] No working camera found on /dev/video0 or /dev/video1.")
        print("Please ensure your webcam is plugged in and permissions are granted.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    engine = VisionGestureEngine()
    if engine.landmarker is None:
        print("[ERROR] Failed to load MediaPipe HandLandmarker model.")
        sys.exit(1)

    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if has_display:
        print("[INFO] Desktop display detected. Opening GUI HUD window...")
        print("Press 'q' in the window to quit.\n")
    else:
        print("[INFO] No desktop display detected. Running in live CLI Console Mode.")
        print("Press Ctrl+C in terminal to quit.\n")

    prev_time = time.time()
    last_printed_gesture = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Failed to grab frame from camera.")
                time.sleep(0.1)
                continue

            # Flip horizontally for natural mirror interaction
            frame = cv2.flip(frame, 1)

            # Process frame with MediaPipe and compute geometric gesture
            gesture_result, annotated_frame = engine.process_bgr_frame(frame, draw_hud=True)

            curr_time = time.time()
            fps = 1.0 / max(1e-6, curr_time - prev_time)
            prev_time = curr_time

            # Console output
            if gesture_result:
                status = "CONFIRMED (HELD)" if gesture_result.stable_held else "Tracking..."
                log_line = (
                    f"\r[HUD] Gesture: {gesture_result.gesture:<12} | "
                    f"Conf: {int(gesture_result.confidence * 100):>3}% | "
                    f"Hold: {gesture_result.hold_duration_sec:.1f}s | "
                    f"Status: {status:<18} | FPS: {int(fps):>2}"
                )
                sys.stdout.write(log_line)
                sys.stdout.flush()
                last_printed_gesture = gesture_result.gesture
            else:
                if last_printed_gesture is not None:
                    sys.stdout.write(f"\r[HUD] Hand not in frame... Searching camera feed...{' ' * 25}\r")
                    sys.stdout.flush()
                    last_printed_gesture = None

            if has_display:
                # Draw FPS on GUI
                cv2.putText(
                    annotated_frame,
                    f"FPS: {int(fps)}",
                    (annotated_frame.shape[1] - 100, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255),
                    2
                )
                cv2.imshow("OmniKiosk - Module 4 Live Gesture HUD", annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user (Ctrl+C).")

    cap.release()
    if has_display:
        cv2.destroyAllWindows()
    print("\n[INFO] Live camera demo closed cleanly.")


if __name__ == "__main__":
    main()
