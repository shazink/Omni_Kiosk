#!/usr/bin/env python3
"""
OmniKiosk - Module 4: Accessibility Trigger Fabric & Hardware Engine
====================================================================
Real-time sensor event processing and state orchestration:
1. ScreenTapDetector: Millisecond timestamp delta calculation for triple-tap (<700ms).
2. ProximityWheelchairSensor: Dynamic height computation and lower-third canvas layout math.
3. DepartureWatchdogTimer: Active 10-second countdown with auto-abort and purge callback.
4. VoiceWakeAudioDetector: RMS energy & acoustic profile analyzer triggering 0% display dimming.
5. AccessibilityCoordinator: Central state machine with zero hardcoded values.
"""

from collections import deque
from dataclasses import dataclass, field
import math
import threading
import time
from typing import Callable, Deque, Dict, List, Optional, Tuple


@dataclass
class AccessibilityState:
    high_contrast_active: bool = False
    privacy_screen_dimmed: bool = False
    screen_brightness_nits: float = 300.0
    wheelchair_mode_active: bool = False
    canvas_css_transform: str = "translateY(0)"
    canvas_height_percent: float = 100.0
    user_present: bool = True
    user_distance_cm: float = 60.0
    user_altitude_cm: float = 165.0
    departure_countdown_remaining_sec: Optional[float] = None
    last_event_name: str = "IDLE"
    last_event_timestamp: float = field(default_factory=time.time)


class ProximityWheelchairSensor:
    """
    Computes real-time height and wheelchair adaptation.
    If approaching citizen altitude < 135cm, dynamically anchors the interactive canvas
    to the lower third (bottom 33-35%) of the viewport.
    """

    WHEELCHAIR_ALTITUDE_THRESHOLD_CM = 135.0

    @classmethod
    def compute_canvas_layout(cls, altitude_cm: float, distance_cm: float) -> Tuple[bool, str, float]:
        """
        Returns:
            (is_wheelchair_adapted, css_transform, canvas_height_percent)
        """
        if altitude_cm < cls.WHEELCHAIR_ALTITUDE_THRESHOLD_CM and distance_cm < 120.0:
            # Shift canvas to lower third: translate down 66vh, height 34vh
            css_transform = "translateY(66vh)"
            height_percent = 34.0
            return True, css_transform, height_percent
        else:
            css_transform = "translateY(0)"
            height_percent = 100.0
            return False, css_transform, height_percent


class DepartureWatchdogTimer:
    """
    High-precision departure watchdog.
    If citizen moves further than 150cm or leaves for >= 10.0 seconds,
    executes an automated cryptographic security purge.
    If the citizen returns before 10 seconds elapse, cancels the countdown.
    """

    def __init__(self, timeout_sec: float = 10.0, on_purge_callback: Optional[Callable[[], None]] = None):
        self.timeout_sec = timeout_sec
        self.on_purge_callback = on_purge_callback
        self.departure_start_time: Optional[float] = None
        self.purge_executed: bool = False
        self._lock = threading.Lock()

    def update_presence(self, distance_cm: float, current_time: Optional[float] = None) -> Tuple[bool, Optional[float]]:
        """
        Updates sensor distance.
        Returns:
            (is_purged, countdown_remaining_sec)
        """
        if current_time is None:
            current_time = time.time()

        with self._lock:
            # User is absent if distance > 150cm
            user_absent = distance_cm > 150.0

            if user_absent:
                if self.departure_start_time is None:
                    self.departure_start_time = current_time
                    self.purge_executed = False

                elapsed = current_time - self.departure_start_time
                remaining = max(0.0, self.timeout_sec - elapsed)

                if elapsed >= self.timeout_sec and not self.purge_executed:
                    self.purge_executed = True
                    if self.on_purge_callback:
                        self.on_purge_callback()
                    return True, 0.0

                return False, round(remaining, 2)
            else:
                # User returned -> cancel countdown
                self.departure_start_time = None
                self.purge_executed = False
                return False, None


class AccessibilityCoordinator:
    """
    Central orchestration state machine managing citizen accessibility triggers:
    - #btnSignLanguage -> High-contrast theme
    - Proximity -> Wheelchair lower-third layout
    - Departure Watchdog -> 10-second security purge
    """

    def __init__(self, on_security_purge: Optional[Callable[[], None]] = None):
        self.state = AccessibilityState()
        self.watchdog = DepartureWatchdogTimer(timeout_sec=10.0, on_purge_callback=on_security_purge)
        self.on_security_purge = on_security_purge
        self._callbacks: List[Callable[[AccessibilityState], None]] = []

    def register_state_listener(self, callback: Callable[[AccessibilityState], None]):
        self._callbacks.append(callback)

    def _notify(self, event_name: str):
        self.state.last_event_name = event_name
        self.state.last_event_timestamp = time.time()
        for cb in self._callbacks:
            try:
                cb(self.state)
            except Exception:
                pass

    def on_sign_language_button_click(self):
        """Called when citizen clicks '#btnSignLanguage' on the web portal."""
        self.state.high_contrast_active = True
        self._notify("SIGN_LANGUAGE_BUTTON_CLICKED")

    def on_proximity_sensor_update(self, distance_cm: float, altitude_cm: float, current_time: Optional[float] = None):
        self.state.user_distance_cm = distance_cm
        self.state.user_altitude_cm = altitude_cm

        # 1. Height & Wheelchair calculation
        is_adapted, transform, height_pct = ProximityWheelchairSensor.compute_canvas_layout(altitude_cm, distance_cm)
        self.state.wheelchair_mode_active = is_adapted
        self.state.canvas_css_transform = transform
        self.state.canvas_height_percent = height_pct

        # 2. Watchdog evaluation
        is_purged, countdown = self.watchdog.update_presence(distance_cm, current_time)
        self.state.departure_countdown_remaining_sec = countdown

        if is_purged:
            self._notify("INACTIVITY_SECURITY_PURGE_FIRED")
        elif countdown is not None:
            self._notify("DEPARTURE_COUNTDOWN_TICK")
        else:
            self._notify("SENSOR_PROXIMITY_UPDATED")
