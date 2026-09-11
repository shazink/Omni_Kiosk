"""
OmniKiosk - Hardware Sensor Fabric Simulator (`kiosk_hardware_sim.py`)
Simulates:
1. Tactile / Haptic vibrating motor actuator (for DEAFBLIND_MODE)
2. 40-cell Refreshable Braille pin display (for DEAFBLIND_MODE)
3. Voice-Wake detector ("Help me register") with screen dimming
4. Screen Triple-Tap gesture detector (<700ms)
5. Ultrasonic proximity & wheelchair altitude adapter (<135cm canvas drop)
6. 10-second departure inactivity watchdog & emergency memory scrubber
"""

import time
import logging
from typing import Dict, Any, List, Optional, Callable
from governance_and_purge import (
    MockTactileDevice,
    MockBrailleDisplay,
    TactileEvent,
    TACTILE_PATTERNS
)

logger = logging.getLogger("OmniKiosk.HardwareSim")


class VoiceWakeDetector:
    """Simulates low-power voice wake-word detection ("Help me register")."""
    def __init__(self, wake_phrase: str = "help me register"):
        self.wake_phrase = wake_phrase.lower()
        self.is_listening = True

    def process_audio_phrase(self, spoken_text: str) -> bool:
        """Evaluates spoken speech string for wake intent."""
        clean = spoken_text.lower().strip()
        if self.wake_phrase in clean:
            logger.info(f"[VOICE_WAKE] Detected wake phrase: '{spoken_text}' -> Triggering Privacy Screen Dim & Audio Session")
            return True
        return False


class TripleTapScreenDetector:
    """Detects 3 rapid taps (<700ms) anywhere on the kiosk glass display."""
    def __init__(self, max_interval_ms: float = 700.0):
        self.max_interval_ms = max_interval_ms
        self.tap_timestamps: List[float] = []

    def record_tap(self, timestamp: Optional[float] = None) -> bool:
        """Records a tap event and returns True if triple-tap threshold is reached."""
        now = (timestamp or time.time()) * 1000.0  # convert to ms
        self.tap_timestamps.append(now)
        
        # Keep only last 3 taps
        if len(self.tap_timestamps) > 3:
            self.tap_timestamps = self.tap_timestamps[-3:]

        if len(self.tap_timestamps) == 3:
            delta = self.tap_timestamps[2] - self.tap_timestamps[0]
            if delta <= self.max_interval_ms:
                logger.info(f"[TOUCH_SENSOR] Triple-tap detected ({delta:.1f}ms < {self.max_interval_ms}ms) -> Triggering High-Contrast Accessibility Mode")
                self.tap_timestamps.clear()
                return True

        return False


class UltrasonicProximitySensor:
    """
    Simulates dual ultrasonic sensors:
    1. Height/Altitude sensor (Wheelchair detection < 135cm)
    2. Range/Distance sensor (Citizen presence / departure > 150cm)
    """
    def __init__(self, departure_threshold_cm: float = 150.0, wheelchair_height_cm: float = 135.0):
        self.departure_threshold_cm = departure_threshold_cm
        self.wheelchair_height_cm = wheelchair_height_cm
        self.current_distance_cm = 50.0  # default citizen standing in front
        self.current_height_cm = 165.0   # default standing adult height

    def update_telemetry(self, distance_cm: float, height_cm: float) -> Dict[str, Any]:
        """Updates simulated ultrasonic sensor telemetry."""
        self.current_distance_cm = distance_cm
        self.current_height_cm = height_cm
        
        is_wheelchair = height_cm < self.wheelchair_height_cm
        is_departed = distance_cm > self.departure_threshold_cm

        return {
            "distance_cm": distance_cm,
            "height_cm": height_cm,
            "is_wheelchair_adapted": is_wheelchair,
            "is_citizen_present": not is_departed,
            "recommended_ui_anchor": "LOWER_THIRD" if is_wheelchair else "FULL_DISPLAY"
        }


class HardwareFabricSimulator:
    """
    Unified Hardware Sensor and Actuator Fabric for OmniKiosk.
    Combines Tactile, Braille, Voice, Touch, and Ultrasonic Subsystems.
    """
    def __init__(self):
        self.tactile_device = MockTactileDevice(device_id="KIOSK_TACTILE_ACTUATOR_01")
        self.braille_display = MockBrailleDisplay(cell_count=40)
        self.voice_wake = VoiceWakeDetector()
        self.touch_sensor = TripleTapScreenDetector()
        self.ultrasonic = UltrasonicProximitySensor()
        self.screen_brightness: int = 100  # 0% to 100%
        self.high_contrast_active: bool = False
        self.ui_canvas_position: str = "FULL_DISPLAY"

    def trigger_voice_wake(self, phrase: str = "help me register") -> bool:
        """Simulates voice-wake trigger."""
        if self.voice_wake.process_audio_phrase(phrase):
            self.screen_brightness = 0  # Privacy display dimming
            logger.info("[HARDWARE_FABRIC] Screen brightness dimmed to 0% for audio privacy.")
            return True
        return False

    def trigger_triple_tap(self) -> bool:
        """Simulates triple-tap screen trigger."""
        t = time.time()
        self.touch_sensor.record_tap(t)
        self.touch_sensor.record_tap(t + 0.15)
        res = self.touch_sensor.record_tap(t + 0.30)
        if res:
            self.high_contrast_active = True
            logger.info("[HARDWARE_FABRIC] High-contrast accessibility theme activated.")
        return res

    def set_citizen_position(self, distance_cm: float, height_cm: float) -> Dict[str, Any]:
        """Simulates citizen distance and height reading."""
        telemetry = self.ultrasonic.update_telemetry(distance_cm, height_cm)
        self.ui_canvas_position = telemetry["recommended_ui_anchor"]
        if telemetry["is_wheelchair_adapted"]:
            logger.info("[HARDWARE_FABRIC] Wheelchair detected -> Canvas dropped to lower 33% of display.")
        return telemetry

    def render_tactile_status(self) -> str:
        """Returns visual simulator representation of current tactile state."""
        return (
            f"┌────────────────────────────────────────────────────────┐\n"
            f"│ TACTILE DEVICE SIMULATOR                               │\n"
            f"│ Last Signal: {self.tactile_device.get_last_signal_display():<41} │\n"
            f"│ Braille ASCII: {self.braille_display.current_text:<39} │\n"
            f"│ Braille Pins : {self.braille_display.current_braille:<39} │\n"
            f"│ Hardware Inputs: [A: CONFIRM]  [B: CANCEL]             │\n"
            f"└────────────────────────────────────────────────────────┘"
        )
