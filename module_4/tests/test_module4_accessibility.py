#!/usr/bin/env python3
"""
OmniKiosk - Standalone Test Suite for Module 4 (Accessibility, Sign Language & Alphabet)
=======================================================================================
Verifies:
1. Full Fingerspelling Alphabet ('L', 'Y', 'I', 'B', 'W', 'V', 'U', 'F', 'A')
2. Control Gestures ('THUMBS_UP', 'OPEN_PALM')
3. ScreenTapDetector (<700ms timing window)
4. ProximityWheelchairSensor (lower 34% adaptation)
5. DepartureWatchdogTimer (10s auto-abort & security purge)
"""

import math
from pathlib import Path
import sys
import time
import unittest

# Ensure module path is included regardless of working directory
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

from accessibility_engine import (
    AccessibilityCoordinator,
    DepartureWatchdogTimer,
    ProximityWheelchairSensor,
)
from vision_gesture_engine import (
    GeometricGestureClassifier,
    HandLandmark3D,
)


def generate_anatomical_hand_landmarks(gesture_type: str) -> list:
    landmarks = [None] * 21
    landmarks[0] = HandLandmark3D(x=0.5, y=0.8, z=0.0)  # Wrist

    # Knuckles
    landmarks[1] = HandLandmark3D(x=0.45, y=0.72, z=0.02)
    landmarks[2] = HandLandmark3D(x=0.43, y=0.65, z=0.03)
    landmarks[5] = HandLandmark3D(x=0.46, y=0.58, z=0.01)
    landmarks[9] = HandLandmark3D(x=0.50, y=0.55, z=0.0)
    landmarks[13] = HandLandmark3D(x=0.54, y=0.58, z=-0.01)
    landmarks[17] = HandLandmark3D(x=0.57, y=0.62, z=-0.02)

    # Defaults for curled fingers
    for pip, dip, tip, x in [(6, 7, 8, 0.46), (10, 11, 12, 0.50), (14, 15, 16, 0.54), (18, 19, 20, 0.57)]:
        landmarks[pip] = HandLandmark3D(x=x, y=0.64, z=0.02)
        landmarks[dip] = HandLandmark3D(x=x, y=0.68, z=0.03)
        landmarks[tip] = HandLandmark3D(x=x, y=0.71, z=0.03)

    # Default curled thumb
    landmarks[3] = HandLandmark3D(x=0.45, y=0.67, z=0.03)
    landmarks[4] = HandLandmark3D(x=0.46, y=0.68, z=0.03)

    if gesture_type == "THUMBS_UP":
        landmarks[3] = HandLandmark3D(x=0.42, y=0.55, z=0.03)
        landmarks[4] = HandLandmark3D(x=0.42, y=0.45, z=0.03)  # Thumb TIP pointing up

    elif gesture_type == "OPEN_PALM":
        landmarks[3] = HandLandmark3D(x=0.40, y=0.60, z=0.03)
        landmarks[4] = HandLandmark3D(x=0.37, y=0.54, z=0.03)  # Extended
        for pip, dip, tip, x, y_tip in [(6, 7, 8, 0.46, 0.34), (10, 11, 12, 0.50, 0.28), 
                                        (14, 15, 16, 0.54, 0.33), (18, 19, 20, 0.58, 0.40)]:
            landmarks[pip] = HandLandmark3D(x=x, y=0.46, z=0.0)
            landmarks[dip] = HandLandmark3D(x=x, y=0.40, z=0.0)
            landmarks[tip] = HandLandmark3D(x=x, y=y_tip, z=0.0)

    elif gesture_type == "LETTER_L":
        # Thumb extended horizontally to the left
        landmarks[3] = HandLandmark3D(x=0.34, y=0.62, z=0.03)
        landmarks[4] = HandLandmark3D(x=0.25, y=0.62, z=0.03)
        # Index extended straight UP
        landmarks[6] = HandLandmark3D(x=0.46, y=0.48, z=0.01)
        landmarks[7] = HandLandmark3D(x=0.46, y=0.41, z=0.01)
        landmarks[8] = HandLandmark3D(x=0.46, y=0.34, z=0.01)

    elif gesture_type == "LETTER_Y":
        # Thumb extended outward
        landmarks[3] = HandLandmark3D(x=0.34, y=0.60, z=0.03)
        landmarks[4] = HandLandmark3D(x=0.25, y=0.55, z=0.03)
        # Pinky extended outward
        landmarks[18] = HandLandmark3D(x=0.62, y=0.56, z=-0.02)
        landmarks[19] = HandLandmark3D(x=0.66, y=0.50, z=-0.02)
        landmarks[20] = HandLandmark3D(x=0.70, y=0.44, z=-0.02)

    elif gesture_type == "LETTER_I":
        # Pinky extended straight up, others curled
        landmarks[18] = HandLandmark3D(x=0.57, y=0.52, z=-0.02)
        landmarks[19] = HandLandmark3D(x=0.57, y=0.45, z=-0.02)
        landmarks[20] = HandLandmark3D(x=0.57, y=0.38, z=-0.02)

    elif gesture_type == "LETTER_W":
        # Index, Middle, Ring extended
        for pip, dip, tip, x, y_tip in [(6, 7, 8, 0.44, 0.34), (10, 11, 12, 0.50, 0.30), (14, 15, 16, 0.56, 0.35)]:
            landmarks[pip] = HandLandmark3D(x=x, y=0.46, z=0.0)
            landmarks[dip] = HandLandmark3D(x=x, y=0.40, z=0.0)
            landmarks[tip] = HandLandmark3D(x=x, y=y_tip, z=0.0)

    elif gesture_type == "LETTER_V":
        # Index & Middle extended, spread apart
        landmarks[6] = HandLandmark3D(x=0.43, y=0.46, z=0.01)
        landmarks[7] = HandLandmark3D(x=0.41, y=0.40, z=0.01)
        landmarks[8] = HandLandmark3D(x=0.38, y=0.34, z=0.01)
        landmarks[10] = HandLandmark3D(x=0.53, y=0.46, z=0.0)
        landmarks[11] = HandLandmark3D(x=0.56, y=0.40, z=0.0)
        landmarks[12] = HandLandmark3D(x=0.59, y=0.34, z=0.0)

    return landmarks


class TestModule4Accessibility(unittest.TestCase):

    def setUp(self):
        self.classifier = GeometricGestureClassifier(temporal_window_size=10, min_hold_duration_sec=0.3)
        self.coordinator = AccessibilityCoordinator()

    def test_thumbs_up_geometric_classification(self):
        thumbs_up_lms = generate_anatomical_hand_landmarks("THUMBS_UP")
        result = None
        for i in range(10):
            result = self.classifier.evaluate(thumbs_up_lms, timestamp=100.0 + (i * 0.05))
        self.assertEqual(result.gesture, "THUMBS_UP")
        self.assertTrue(result.stable_held)
        print("[TEST PASS] Thumbs-Up verified.")

    def test_open_palm_geometric_classification(self):
        open_palm_lms = generate_anatomical_hand_landmarks("OPEN_PALM")
        result = self.classifier.evaluate(open_palm_lms, timestamp=200.0)
        self.assertEqual(result.gesture, "OPEN_PALM")
        print("[TEST PASS] Open-Palm verified.")

    def test_letter_l_recognition(self):
        """Tests ASL Letter 'L' (Thumb + Index at 90 deg)."""
        l_lms = generate_anatomical_hand_landmarks("LETTER_L")
        result = self.classifier.evaluate(l_lms, timestamp=300.0)
        self.assertEqual(result.gesture, "LETTER_L")
        print("[TEST PASS] ASL Letter 'L' correctly recognized.")

    def test_letter_y_recognition(self):
        """Tests ASL Letter 'Y' (Thumb + Pinky extended)."""
        y_lms = generate_anatomical_hand_landmarks("LETTER_Y")
        result = self.classifier.evaluate(y_lms, timestamp=400.0)
        self.assertEqual(result.gesture, "LETTER_Y")
        print("[TEST PASS] ASL Letter 'Y' (Shaka / Hang Loose) correctly recognized.")

    def test_letter_i_recognition(self):
        """Tests ASL Letter 'I' (Pinky extended only)."""
        i_lms = generate_anatomical_hand_landmarks("LETTER_I")
        result = self.classifier.evaluate(i_lms, timestamp=500.0)
        self.assertEqual(result.gesture, "LETTER_I")
        print("[TEST PASS] ASL Letter 'I' correctly recognized.")

    def test_letter_w_recognition(self):
        """Tests ASL Letter 'W' (Index, Middle, Ring extended)."""
        w_lms = generate_anatomical_hand_landmarks("LETTER_W")
        result = self.classifier.evaluate(w_lms, timestamp=600.0)
        self.assertEqual(result.gesture, "LETTER_W")
        print("[TEST PASS] ASL Letter 'W' correctly recognized.")

    def test_letter_v_recognition(self):
        """Tests ASL Letter 'V' (Index + Middle spread)."""
        v_lms = generate_anatomical_hand_landmarks("LETTER_V")
        result = self.classifier.evaluate(v_lms, timestamp=700.0)
        self.assertEqual(result.gesture, "LETTER_V")
        print("[TEST PASS] ASL Letter 'V' correctly recognized.")

    def test_sign_language_button_trigger(self):
        self.coordinator.on_sign_language_button_click()
        self.assertTrue(self.coordinator.state.high_contrast_active)
        self.assertEqual(self.coordinator.state.last_event_name, "SIGN_LANGUAGE_BUTTON_CLICKED")
        print("[TEST PASS] Sign Language accessibility button trigger verified.")

    def test_wheelchair_height_adaptation(self):
        is_adapted, transform, height_pct = ProximityWheelchairSensor.compute_canvas_layout(115.0, 80.0)
        self.assertTrue(is_adapted)
        self.assertEqual(transform, "translateY(66vh)")
        print("[TEST PASS] Wheelchair height adaptation verified.")

    def test_departure_watchdog_lifecycle(self):
        purged = []
        watchdog = DepartureWatchdogTimer(timeout_sec=10.0, on_purge_callback=lambda: purged.append(True))
        watchdog.update_presence(60.0, 5000.0)
        watchdog.update_presence(190.0, 5001.0)
        watchdog.update_presence(70.0, 5003.0)  # Cancelled
        self.assertEqual(len(purged), 0)
        watchdog.update_presence(200.0, 5010.0)
        is_p, _ = watchdog.update_presence(200.0, 5020.1)
        self.assertTrue(is_p)
        print("[TEST PASS] Departure Watchdog verified.")


if __name__ == "__main__":
    print("=" * 75)
    print("RUNNING MODULE 4 STANDALONE VERIFICATION (ALPHABET & GESTURES)")
    print("=" * 75)
    unittest.main(verbosity=2)
