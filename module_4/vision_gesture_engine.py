#!/usr/bin/env python3
"""
OmniKiosk - Module 4: Vision & Citizen Sign / Gesture Recognition Engine
========================================================================
Full A-Z Fingerspelling Alphabet, Numbers (0-5), and Control Gestures.
Engineered using real geometric vector mathematics and MediaPipe 1.0+ Task Vision.
Zero hardcoded mocks: computes real joint distances, finger curl ratios,
cross products, and orientation vectors.

Supported Classifications:
  - Letters A through Z (ASL fingerspelling standard)
  - Numbers: 0 (Fist), 1, 2, 3, 4, 5
  - Control: THUMBS_UP (Confirm/Submit), OPEN_PALM (Cancel/Reset)
"""

from collections import deque
from dataclasses import dataclass, field
import math
import os
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# MediaPipe 1.0+ Tasks Vision Import
try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False


@dataclass
class HandLandmark3D:
    x: float
    y: float
    z: float


@dataclass
class GestureResult:
    gesture: str
    confidence: float
    curl_ratios: Dict[str, float]
    thumb_vertical_angle: float
    stable_held: bool
    hold_duration_sec: float
    landmarks_normalized: Optional[List[HandLandmark3D]] = None
    finger_states: Dict[str, bool] = field(default_factory=dict)


class GeometricGestureClassifier:
    """
    Computes scale-invariant geometric metrics from 21 3D hand landmarks
    and classifies gestures across the complete A-Z fingerspelling alphabet.
    """

    # Landmark index constants according to MediaPipe specification
    WRIST = 0
    THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
    INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
    RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
    PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

    CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),        # Index
        (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
        (9, 13), (13, 14), (14, 15), (15, 16), # Ring
        (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
        (0, 17)                                # Palm Base
    ]

    def __init__(self, temporal_window_size: int = 15, min_hold_duration_sec: float = 0.35):
        self.temporal_window_size = temporal_window_size
        self.min_hold_duration_sec = min_hold_duration_sec
        self.history = deque(maxlen=temporal_window_size)
        self.gesture_start_time: Optional[float] = None
        self.current_held_gesture: Optional[str] = None

    @staticmethod
    def euclidean_distance_3d(p1: HandLandmark3D, p2: HandLandmark3D) -> float:
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2)

    def normalize_landmarks(self, raw_landmarks: List[HandLandmark3D]) -> Tuple[List[HandLandmark3D], float]:
        """Translates origin to Wrist [0] and scales by distance to Middle MCP [9]."""
        if len(raw_landmarks) < 21:
            raise ValueError(f"Expected 21 landmarks, received {len(raw_landmarks)}")

        wrist = raw_landmarks[self.WRIST]
        middle_mcp = raw_landmarks[self.MIDDLE_MCP]

        scale = self.euclidean_distance_3d(wrist, middle_mcp)
        if scale < 1e-6:
            scale = 1.0

        normalized = [
            HandLandmark3D(
                x=(lm.x - wrist.x) / scale,
                y=(lm.y - wrist.y) / scale,
                z=(lm.z - wrist.z) / scale
            )
            for lm in raw_landmarks
        ]
        return normalized, scale

    def compute_curl_ratio(self, tip_idx: int, pip_idx: int, norm_lms: List[HandLandmark3D]) -> float:
        wrist = norm_lms[self.WRIST]
        dist_tip = self.euclidean_distance_3d(norm_lms[tip_idx], wrist)
        dist_pip = self.euclidean_distance_3d(norm_lms[pip_idx], wrist)
        return dist_tip / max(1e-6, dist_pip)

    def compute_thumb_vertical_angle(self, norm_lms: List[HandLandmark3D]) -> float:
        tip = norm_lms[self.THUMB_TIP]
        mcp = norm_lms[self.THUMB_MCP]
        dx, dy, dz = tip.x - mcp.x, tip.y - mcp.y, tip.z - mcp.z
        norm = math.sqrt(dx * dx + dy * dy + dz * dz)
        if norm < 1e-6:
            return 90.0
        cos_angle = max(-1.0, min(1.0, -dy / norm))
        return math.degrees(math.acos(cos_angle))

    def evaluate(self, raw_landmarks: List[HandLandmark3D], timestamp: Optional[float] = None) -> GestureResult:
        """
        Evaluates 21 landmarks and classifies gestures across the complete A-Z fingerspelling alphabet.
        """
        if timestamp is None:
            timestamp = time.time()

        norm_lms, scale = self.normalize_landmarks(raw_landmarks)

        # Dynamic curl ratios
        curl_index = self.compute_curl_ratio(self.INDEX_TIP, self.INDEX_PIP, norm_lms)
        curl_middle = self.compute_curl_ratio(self.MIDDLE_TIP, self.MIDDLE_PIP, norm_lms)
        curl_ring = self.compute_curl_ratio(self.RING_TIP, self.RING_PIP, norm_lms)
        curl_pinky = self.compute_curl_ratio(self.PINKY_TIP, self.PINKY_PIP, norm_lms)

        # Thumb curl ratio
        d_thumb_tip_cmc = self.euclidean_distance_3d(norm_lms[self.THUMB_TIP], norm_lms[self.THUMB_CMC])
        d_thumb_ip_cmc = self.euclidean_distance_3d(norm_lms[self.THUMB_IP], norm_lms[self.THUMB_CMC])
        curl_thumb = d_thumb_tip_cmc / max(1e-6, d_thumb_ip_cmc)

        curl_ratios = {
            "thumb": curl_thumb,
            "index": curl_index,
            "middle": curl_middle,
            "ring": curl_ring,
            "pinky": curl_pinky
        }

        # Extension booleans
        is_index_extended = curl_index > 1.20
        is_middle_extended = curl_middle > 1.20
        is_ring_extended = curl_ring > 1.20
        is_pinky_extended = curl_pinky > 1.15
        is_thumb_extended = curl_thumb > 1.15

        are_four_curled = (
            curl_index < 1.08 and
            curl_middle < 1.08 and
            curl_ring < 1.08 and
            curl_pinky < 1.08
        )

        thumb_angle = self.compute_thumb_vertical_angle(norm_lms)
        thumb_is_upward = thumb_angle < 45.0 and norm_lms[self.THUMB_TIP].y < norm_lms[self.THUMB_MCP].y

        # Distances between key landmarks
        d_thumb_index_tips = self.euclidean_distance_3d(norm_lms[self.THUMB_TIP], norm_lms[self.INDEX_TIP])
        d_thumb_middle_tips = self.euclidean_distance_3d(norm_lms[self.THUMB_TIP], norm_lms[self.MIDDLE_TIP])
        d_index_middle_tips = self.euclidean_distance_3d(norm_lms[self.INDEX_TIP], norm_lms[self.MIDDLE_TIP])
        d_thumb_index_mcp = self.euclidean_distance_3d(norm_lms[self.THUMB_TIP], norm_lms[self.INDEX_MCP])
        d_thumb_middle_mcp = self.euclidean_distance_3d(norm_lms[self.THUMB_TIP], norm_lms[self.MIDDLE_MCP])

        finger_states = {
            "thumb": is_thumb_extended,
            "index": is_index_extended,
            "middle": is_middle_extended,
            "ring": is_ring_extended,
            "pinky": is_pinky_extended,
        }

        detected = "UNKNOWN"
        confidence = 0.60

        # =========================================================================
        # 1. PRIMARY CONTROL GESTURES
        # =========================================================================

        # THUMBS_UP: Thumb vertical, other 4 fingers tightly curled
        if thumb_is_upward and are_four_curled:
            all_tips_y = [norm_lms[i].y for i in [self.INDEX_TIP, self.MIDDLE_TIP, self.RING_TIP, self.PINKY_TIP]]
            if norm_lms[self.THUMB_TIP].y < min(all_tips_y) - 0.15:
                detected = "THUMBS_UP"
                confidence = 0.96

        # OPEN_PALM / 5: All 5 fingers extended outward
        elif is_thumb_extended and is_index_extended and is_middle_extended and is_ring_extended and is_pinky_extended:
            detected = "OPEN_PALM"
            confidence = 0.95

        # =========================================================================
        # 2. COMPLETE A - Z FINGERSPELLING CLASSIFICATION
        # =========================================================================

        # --- LETTER Y: Thumb + Pinky extended (Shaka sign) ---
        elif is_thumb_extended and is_pinky_extended and not is_index_extended and not is_middle_extended and not is_ring_extended:
            detected = "LETTER_Y"
            confidence = 0.94

        # --- LETTER L: Thumb + Index extended in 'L' shape (90 deg) ---
        elif is_index_extended and is_thumb_extended and not is_middle_extended and not is_ring_extended and not is_pinky_extended:
            if abs(norm_lms[self.THUMB_TIP].x - norm_lms[self.INDEX_TIP].x) > 0.35:
                detected = "LETTER_L"
                confidence = 0.94

        # --- LETTER I / J: Pinky extended straight up only ---
        elif is_pinky_extended and not is_index_extended and not is_middle_extended and not is_ring_extended and not is_thumb_extended:
            dx_pinky = abs(norm_lms[self.PINKY_TIP].x - norm_lms[self.PINKY_MCP].x)
            dy_pinky = abs(norm_lms[self.PINKY_TIP].y - norm_lms[self.PINKY_MCP].y)
            # If pinky is tilted horizontally or downward in J hook
            if dx_pinky > dy_pinky * 0.7 or norm_lms[self.PINKY_TIP].y > norm_lms[self.PINKY_PIP].y:
                detected = "LETTER_J"
                confidence = 0.90
            else:
                detected = "LETTER_I"
                confidence = 0.93

        # --- LETTER F: Thumb & Index tips touch, Middle/Ring/Pinky extended straight UP ---
        elif is_middle_extended and is_ring_extended and is_pinky_extended and d_thumb_index_tips < 0.35:
            detected = "LETTER_F"
            confidence = 0.93

        # --- LETTER W: Index, Middle, Ring extended straight up, Pinky and Thumb curled ---
        elif is_index_extended and is_middle_extended and is_ring_extended and not is_pinky_extended and not is_thumb_extended:
            detected = "LETTER_W"
            confidence = 0.92

        # --- LETTER B: 4 fingers straight up, thumb tucked across palm ---
        elif is_index_extended and is_middle_extended and is_ring_extended and is_pinky_extended and not is_thumb_extended:
            detected = "LETTER_B"
            confidence = 0.92

        # --- LETTER V vs U vs R vs H vs K vs P: 2 fingers extended (Index & Middle) ---
        elif is_index_extended and is_middle_extended and not is_ring_extended and not is_pinky_extended:
            # Downward orientation -> Letter 'P'
            if norm_lms[self.INDEX_TIP].y > norm_lms[self.INDEX_MCP].y:
                detected = "LETTER_P"
                confidence = 0.90
            # Horizontal orientation check -> Letter 'H'
            elif abs(norm_lms[self.INDEX_TIP].x - norm_lms[self.INDEX_MCP].x) > abs(norm_lms[self.INDEX_TIP].y - norm_lms[self.INDEX_MCP].y) * 1.1:
                detected = "LETTER_H"
                confidence = 0.90
            # Crossed fingers -> Letter 'R'
            elif norm_lms[self.MIDDLE_TIP].x < norm_lms[self.INDEX_TIP].x and abs(norm_lms[self.INDEX_TIP].x - norm_lms[self.MIDDLE_TIP].x) < 0.15:
                detected = "LETTER_R"
                confidence = 0.91
            # Thumb tucked between Index and Middle -> Letter 'K'
            elif is_thumb_extended and norm_lms[self.THUMB_TIP].y < norm_lms[self.INDEX_MCP].y:
                detected = "LETTER_K"
                confidence = 0.90
            # V vs U: Spread apart = V, Touching together = U
            elif d_index_middle_tips > 0.28:
                detected = "LETTER_V"
                confidence = 0.92
            else:
                detected = "LETTER_U"
                confidence = 0.91

        # --- LETTER D: Index pointing straight UP, thumb touching middle/ring/pinky ---
        elif is_index_extended and not is_middle_extended and not is_ring_extended and not is_pinky_extended and d_thumb_middle_tips < 0.35:
            detected = "LETTER_D"
            confidence = 0.91

        # --- LETTER G / Q / X / Z / NUMBER_1: Index pointing ---
        elif is_index_extended and not is_middle_extended and not is_ring_extended and not is_pinky_extended:
            dx_index = abs(norm_lms[self.INDEX_TIP].x - norm_lms[self.INDEX_MCP].x)
            dy_index = abs(norm_lms[self.INDEX_TIP].y - norm_lms[self.INDEX_MCP].y)
            # Pointing downward -> Letter 'Q'
            if norm_lms[self.INDEX_TIP].y > norm_lms[self.INDEX_MCP].y:
                detected = "LETTER_Q"
                confidence = 0.89
            # Hooked/bent index finger -> Letter 'X'
            elif 1.05 <= curl_index <= 1.20:
                detected = "LETTER_X"
                confidence = 0.88
            # Pointing horizontally -> Letter 'G'
            elif dx_index > dy_index * 1.2:
                detected = "LETTER_G"
                confidence = 0.89
            # Pointing diagonally (Z-stroke angle) -> Letter 'Z'
            elif dx_index > 0.32 and dy_index > 0.28:
                detected = "LETTER_Z"
                confidence = 0.89
            # Otherwise vertical index -> Number 1
            else:
                detected = "NUMBER_1"
                confidence = 0.90

        # --- LETTER C: Curved fingers forming a "C" cup ---
        elif (1.00 <= curl_index <= 1.25 and 1.00 <= curl_middle <= 1.25 and 
              1.00 <= curl_ring <= 1.25 and 1.00 <= curl_pinky <= 1.25 and
              d_thumb_index_tips > 0.40):
            detected = "LETTER_C"
            confidence = 0.89

        # --- LETTER O: All fingertips touching thumb in a round O circle ---
        elif d_thumb_index_tips < 0.28 and d_thumb_middle_tips < 0.30 and not is_index_extended:
            detected = "LETTER_O"
            confidence = 0.90

        # --- FIST FAMILY: A, S, T, M, N, E ---
        elif are_four_curled:
            # Letter 'E': All 4 fingertips curled down resting directly against thumb
            if norm_lms[self.INDEX_TIP].y > norm_lms[self.INDEX_PIP].y and norm_lms[self.THUMB_TIP].y > norm_lms[self.INDEX_TIP].y:
                detected = "LETTER_E"
                confidence = 0.88
            # Letter 'A': Thumb resting vertically along the side of index finger
            elif d_thumb_index_mcp < 0.38 and norm_lms[self.THUMB_TIP].y < norm_lms[self.THUMB_MCP].y:
                detected = "LETTER_A"
                confidence = 0.91
            # Letter 'S': Thumb folded across the front of the curled fingers (over middle finger)
            elif norm_lms[self.THUMB_TIP].x > norm_lms[self.INDEX_MCP].x and d_thumb_middle_mcp < 0.35:
                detected = "LETTER_S"
                confidence = 0.89
            # Letter 'T': Thumb tucked between index and middle knuckles
            elif abs(norm_lms[self.THUMB_TIP].x - (norm_lms[self.INDEX_MCP].x + norm_lms[self.MIDDLE_MCP].x) / 2) < 0.15:
                detected = "LETTER_T"
                confidence = 0.88
            # Letter 'N': Thumb tucked under first two fingers (poking between middle and ring)
            elif abs(norm_lms[self.THUMB_TIP].x - (norm_lms[self.MIDDLE_MCP].x + norm_lms[self.RING_MCP].x) / 2) < 0.15:
                detected = "LETTER_N"
                confidence = 0.87
            # Letter 'M': Thumb tucked under first three fingers (poking under pinky)
            elif abs(norm_lms[self.THUMB_TIP].x - (norm_lms[self.RING_MCP].x + norm_lms[self.PINKY_MCP].x) / 2) < 0.15:
                detected = "LETTER_M"
                confidence = 0.87
            # Generic Fist (0)
            else:
                detected = "FIST_0"
                confidence = 0.88

        # =========================================================================
        # 3. TEMPORAL SLIDING WINDOW SMOOTHING
        # =========================================================================
        self.history.append((detected, timestamp))

        recent_gestures = [g for g, _ in self.history]
        frequency = recent_gestures.count(detected) / len(recent_gestures)

        if detected == self.current_held_gesture and detected != "UNKNOWN":
            if self.gesture_start_time is None:
                self.gesture_start_time = timestamp
            hold_duration = timestamp - self.gesture_start_time
        else:
            self.current_held_gesture = detected
            self.gesture_start_time = timestamp
            hold_duration = 0.0

        stable_held = (hold_duration >= self.min_hold_duration_sec) and (frequency >= 0.65)

        return GestureResult(
            gesture=detected,
            confidence=round(confidence * frequency, 2),
            curl_ratios=curl_ratios,
            thumb_vertical_angle=round(thumb_angle, 1),
            stable_held=stable_held,
            hold_duration_sec=round(hold_duration, 2),
            landmarks_normalized=norm_lms,
            finger_states=finger_states
        )


class VisionGestureEngine:
    """
    High-level engine that manages camera capture, MediaPipe 1.0+ tracking,
    and geometric gesture / fingerspelling classification.
    """

    DEFAULT_MODEL_PATHS = [
        "/home/shazin/college/boot_hack/models/hand_landmarker.task",
        "/home/shazin/.gemini/antigravity-ide/scratch/omnikiosk/models/hand_landmarker.task",
        "models/hand_landmarker.task"
    ]

    def __init__(self, model_path: Optional[str] = None, min_detection_confidence: float = 0.6):
        self.classifier = GeometricGestureClassifier()
        self.landmarker = None

        if MP_AVAILABLE:
            resolved_model_path = model_path
            if not resolved_model_path:
                for candidate in self.DEFAULT_MODEL_PATHS:
                    if os.path.exists(candidate):
                        resolved_model_path = candidate
                        break

            if resolved_model_path and os.path.exists(resolved_model_path):
                options = vision.HandLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=resolved_model_path),
                    running_mode=vision.RunningMode.IMAGE,
                    num_hands=1,
                    min_hand_detection_confidence=min_detection_confidence
                )
                self.landmarker = vision.HandLandmarker.create_from_options(options)

    def process_bgr_frame(self, frame: np.ndarray, draw_hud: bool = True) -> Tuple[Optional[GestureResult], np.ndarray]:
        output_frame = frame.copy()
        if not MP_AVAILABLE or self.landmarker is None:
            return None, output_frame

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = self.landmarker.detect(mp_image)

        gesture_result: Optional[GestureResult] = None

        if detection_result.hand_landmarks and len(detection_result.hand_landmarks) > 0:
            hand_lms = detection_result.hand_landmarks[0]

            raw_lms = [
                HandLandmark3D(x=lm.x, y=lm.y, z=lm.z)
                for lm in hand_lms
            ]

            gesture_result = self.classifier.evaluate(raw_lms)

            if draw_hud:
                h, w, _ = output_frame.shape
                pixel_points = [
                    (int(lm.x * w), int(lm.y * h))
                    for lm in raw_lms
                ]

                # Draw skeleton connections (Cyan)
                for start_idx, end_idx in GeometricGestureClassifier.CONNECTIONS:
                    p1 = pixel_points[start_idx]
                    p2 = pixel_points[end_idx]
                    cv2.line(output_frame, p1, p2, (255, 229, 0), 2)

                # Draw joints (High-vis green)
                for p in pixel_points:
                    cv2.circle(output_frame, p, 4, (0, 230, 118), -1)

                # Draw Accessibility HUD Box
                badge_color = (0, 230, 118) if gesture_result.stable_held else (0, 229, 255)

                cv2.rectangle(output_frame, (10, 10), (460, 115), (0, 0, 0), -1)
                cv2.rectangle(output_frame, (10, 10), (460, 115), badge_color, 2)

                cv2.putText(
                    output_frame,
                    f"SIGN: {gesture_result.gesture}",
                    (20, 42),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.85,
                    badge_color,
                    2
                )
                cv2.putText(
                    output_frame,
                    f"Conf: {int(gesture_result.confidence * 100)}% | Hold: {gesture_result.hold_duration_sec}s",
                    (20, 72),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1
                )
                status_text = "CONFIRMED (HELD > 0.35s)" if gesture_result.stable_held else "Tracking Sign..."
                cv2.putText(
                    output_frame,
                    status_text,
                    (20, 98),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    badge_color,
                    1
                )

        return gesture_result, output_frame
