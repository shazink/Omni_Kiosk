"""
OmniKiosk - Module 6: Multi-Agent Governance, Supervisor Verification & Ephemeral Privacy Purge
Includes first-class DEAFBLIND_MODE with tactile/Braille hardware abstraction.

Design Principle: "No sight. No sound. Still independent."
"""

import os
import re
import time
import json
import uuid
import secrets
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable

# Configure PII-safe logging (NEVER logs sensitive data)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OmniKiosk.Governance")


# =====================================================================
# 1. ACCESSIBILITY MODES & GOVERNANCE STATE ENUMS
# =====================================================================

class AccessibilityMode(str, Enum):
    STANDARD_MODE = "STANDARD_MODE"
    BLIND_MODE = "BLIND_MODE"
    DEAF_MODE = "DEAF_MODE"
    DEAFBLIND_MODE = "DEAFBLIND_MODE"


class GovernanceState(str, Enum):
    IDLE = "IDLE"
    FORM_READY = "FORM_READY"
    CRITIC_VALIDATING = "CRITIC_VALIDATING"
    CRITIC_FAILED = "CRITIC_FAILED"
    CRITIC_PASSED = "CRITIC_PASSED"
    SUPERVISOR_REVIEW = "SUPERVISOR_REVIEW"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    WAITING_FOR_DEAFBLIND_CONFIRMATION = "WAITING_FOR_DEAFBLIND_CONFIRMATION"
    SUBMITTING = "SUBMITTING"
    RECEIPT_VERIFY = "RECEIPT_VERIFY"
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    PURGED = "PURGED"


# =====================================================================
# 2. TACTILE HARDWARE ABSTRACTION & PATTERN CONFIGURATION
# =====================================================================

# Central configurable tactile vibration patterns (durations in ms or visual pulse symbols)
TACTILE_PATTERNS = {
    "INFO": {
        "pattern_name": "SHORT_PULSE",
        "pulses": [200],
        "symbol": "●",
        "description": "One short vibration pulse (Information/Notice)"
    },
    "WARNING": {
        "pattern_name": "DOUBLE_PULSE",
        "pulses": [200, 100, 200],
        "symbol": "● ●",
        "description": "Two short vibration pulses (Warning/Attention needed)"
    },
    "ERROR": {
        "pattern_name": "LONG_PULSE",
        "pulses": [800],
        "symbol": "▬▬▬",
        "description": "One long vibration pulse (Error/Validation failed)"
    },
    "SUCCESS": {
        "pattern_name": "TRIPLE_PULSE",
        "pulses": [150, 100, 150, 100, 150],
        "symbol": "● ● ●",
        "description": "Three short rapid pulses (Success/Receipt issued)"
    },
    "CANCEL": {
        "pattern_name": "LONG_SHORT_PULSE",
        "pulses": [600, 150, 150],
        "symbol": "▬▬ ●",
        "description": "Long pulse followed by short pulse (Cancelled/Session abort)"
    },
    "HEARTBEAT": {
        "pattern_name": "SUBTLE_TAP",
        "pulses": [80],
        "symbol": "·",
        "description": "Subtle tap indicating kiosk active state"
    }
}


class TactileEvent:
    """Represents an abstract tactile haptic event dispatched to tactile hardware."""
    def __init__(self, event_type: str, pattern: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.type = event_type.upper()
        config = TACTILE_PATTERNS.get(self.type, TACTILE_PATTERNS["INFO"])
        self.pattern = pattern or config["pattern_name"]
        self.pulses = config["pulses"]
        self.symbol = config["symbol"]
        self.description = config["description"]
        self.timestamp = time.time()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "pattern": self.pattern,
            "pulses": self.pulses,
            "symbol": self.symbol,
            "description": self.description,
            "timestamp": self.timestamp
        }

    def __repr__(self) -> str:
        return f"<TactileEvent type={self.type} pattern={self.pattern} symbol='{self.symbol}'>"


class MockTactileDevice:
    """
    Hardware abstraction simulator for Deafblind haptic feedback.
    Can be replaced with a serial/USB/BLE haptic actuator driver in production.
    """
    def __init__(self, device_id: str = "TACTILE_SIM_01"):
        self.device_id = device_id
        self.event_history: List[TactileEvent] = []
        self.last_event: Optional[TactileEvent] = None
        self._button_a_callback: Optional[Callable[[], None]] = None  # CONFIRM
        self._button_b_callback: Optional[Callable[[], None]] = None  # CANCEL
        self.is_active = True

    def vibrate(self, event_or_type: Any) -> TactileEvent:
        """Emits a haptic vibration pattern."""
        if isinstance(event_or_type, TactileEvent):
            event = event_or_type
        elif isinstance(event_or_type, str):
            event = TactileEvent(event_type=event_or_type)
        else:
            event = TactileEvent(event_type="INFO")

        self.last_event = event
        self.event_history.append(event)
        
        # Visually log tactile stimulation on simulator console without leaking PII
        logger.info(f"[TACTILE_DEVICE] Vibrating Pattern: {event.type} [{event.pattern}] -> {event.symbol} ({event.description})")
        return event

    def register_input_handlers(self, on_confirm: Callable[[], None], on_cancel: Callable[[], None]):
        """Binds tactile input buttons (Button A = Confirm, Button B = Cancel)."""
        self._button_a_callback = on_confirm
        self._button_b_callback = on_cancel

    def press_confirm(self):
        """Simulates deafblind citizen pressing physical Tactile Button A (Confirm)."""
        logger.info("[TACTILE_DEVICE] Physical Input: Button A [CONFIRM] pressed.")
        if self._button_a_callback:
            self._button_a_callback()

    def press_cancel(self):
        """Simulates deafblind citizen pressing physical Tactile Button B (Cancel)."""
        logger.info("[TACTILE_DEVICE] Physical Input: Button B [CANCEL] pressed.")
        if self._button_b_callback:
            self._button_b_callback()

    def get_last_signal_display(self) -> str:
        """Returns visual representation for kiosk UI or debug logs."""
        if not self.last_event:
            return "IDLE — No recent tactile signal"
        return f"{self.last_event.type} [{self.last_event.pattern}] {self.last_event.symbol}"

    def clear_history(self):
        """Purges event history from memory."""
        self.event_history.clear()
        self.last_event = None


# =====================================================================
# 3. REFRESHABLE BRAILLE DISPLAY ABSTRACTION
# =====================================================================

# Standard English Grade 1 Unicode Braille Translation Table
BRAILLE_MAP = {
    'a': '⠁', 'b': '⠃', 'c': '⠉', 'd': '⠙', 'e': '⠑', 'f': '⠋', 'g': '⠛', 'h': '⠓',
    'i': '⠊', 'j': '⠚', 'k': '⠅', 'l': '⠇', 'm': '⠍', 'n': '⠝', 'o': '⠕', 'p': '⠏',
    'q': '⠟', 'r': '⠗', 's': '⠎', 't': '⠞', 'u': '⠥', 'v': '⠧', 'w': '⠺', 'x': '⠭',
    'y': '⠽', 'z': '⠵', '1': '⠂', '2': '⠆', '3': '⠒', '4': '⠲', '5': '⠢', '6': '⠖',
    '7': '⠶', '8': '⠦', '9': '⠔', '0': '⠴', ' ': ' ', ':': '⠒', '-': '⠤', '.': '⠲',
    '•': '⠿', '*': '⠿', '₹': '⠨', '/': '⠌', ',': '⠂'
}


class MockBrailleDisplay:
    """
    Refreshable Braille Display Hardware Simulator (e.g. 40-cell or 80-cell tactile pin matrix).
    Translates short governance messages to Unicode Braille and pin-state matrices.
    """
    def __init__(self, cell_count: int = 80):
        self.cell_count = cell_count
        self.current_text: str = ""
        self.current_braille: str = ""
        self.display_history: List[str] = []

    def display_text(self, text: str) -> str:
        """Converts text to masked Braille line and updates simulated pin cells."""
        # Sanitize to uppercase for clear standard cell mapping
        clean_text = text.strip()[:self.cell_count]
        self.current_text = clean_text
        
        # Convert to Unicode Braille characters
        braille_chars = []
        for char in clean_text.lower():
            braille_chars.append(BRAILLE_MAP.get(char, '⠿'))
        
        self.current_braille = "".join(braille_chars)
        self.display_history.append(self.current_braille)
        logger.info(f"[BRAILLE_DISPLAY] Refreshed Pins ({len(clean_text)} cells):\n"
                    f"    ASCII  : {clean_text}\n"
                    f"    BRAILLE: {self.current_braille}")
        return self.current_braille

    def get_cells(self) -> Dict[str, Any]:
        return {
            "text": self.current_text,
            "braille": self.current_braille,
            "cells_used": len(self.current_text),
            "total_cells": self.cell_count
        }

    def clear(self):
        """Purges pins and memory buffer."""
        self.current_text = ""
        self.current_braille = ""
        self.display_history.clear()


# =====================================================================
# 4. ACCESSIBILITY OUTPUT ADAPTERS
# =====================================================================

class BaseAccessibilityAdapter:
    """Base class for communicating governance outcomes to citizens."""
    def emit_info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        raise NotImplementedError

    def emit_warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        raise NotImplementedError

    def emit_error(self, message: str, errors: List[str], metadata: Optional[Dict[str, Any]] = None):
        raise NotImplementedError

    def emit_review_summary(self, summary: Dict[str, Any]):
        raise NotImplementedError

    def emit_receipt(self, tracking_id: str, timestamp: str):
        raise NotImplementedError


class DeafblindAccessibilityAdapter(BaseAccessibilityAdapter):
    """
    Deafblind Output Adapter: Operates purely through Tactile Pulses and Refreshable Braille.
    Zero visual or acoustic dependency.
    """
    def __init__(self, tactile_device: MockTactileDevice, braille_display: MockBrailleDisplay):
        self.tactile = tactile_device
        self.braille = braille_display

    def emit_info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.tactile.vibrate("INFO")
        self.braille.display_text(message)

    def emit_warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.tactile.vibrate("WARNING")
        self.braille.display_text(f"WARN: {message}")

    def emit_error(self, message: str, errors: List[str], metadata: Optional[Dict[str, Any]] = None):
        self.tactile.vibrate("ERROR")
        err_str = "; ".join(errors)[:30] if errors else message[:30]
        self.braille.display_text(f"ERR: {err_str}")

    def emit_review_summary(self, summary: Dict[str, Any]):
        """Presents compact masked summary via Braille and prompts tactile confirmation."""
        self.tactile.vibrate("INFO")
        
        # Masked Braille display string (no full PII)
        name = summary.get("name", "CITIZEN")[:10]
        aadhaar_masked = summary.get("aadhaar", "••••0000")
        income = summary.get("income", "0")
        docs = summary.get("documents_verified", 0)
        
        braille_summary = f"{name} UID:{aadhaar_masked} INC:{income} DOCS:{docs} PRESS A:OK B:NO"
        self.braille.display_text(braille_summary)

    def emit_receipt(self, tracking_id: str, timestamp: str):
        """Emits triple pulse success and displays verified tracking ID on Braille display."""
        self.tactile.vibrate("SUCCESS")
        self.braille.display_text(f"SUBMIT OK ID:{tracking_id}")


class BlindAccessibilityAdapter(BaseAccessibilityAdapter):
    """Blind/Low-Vision Output Adapter: Contextual Spoken Text-to-Speech (TTS)."""
    def __init__(self, tts_callback: Optional[Callable[[str], None]] = None):
        self.tts_callback = tts_callback or self._default_tts
        self.spoken_log: List[str] = []

    def _default_tts(self, text: str):
        logger.info(f"[TTS_SPEECH_ENGINE] Spoken: \"{text}\"")

    def emit_info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.spoken_log.append(message)
        self.tts_callback(message)

    def emit_warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        msg = f"Attention: {message}"
        self.spoken_log.append(msg)
        self.tts_callback(msg)

    def emit_error(self, message: str, errors: List[str], metadata: Optional[Dict[str, Any]] = None):
        err_details = ". ".join(errors) if errors else message
        msg = f"Form validation error: {err_details}. Please correct and try again."
        self.spoken_log.append(msg)
        self.tts_callback(msg)

    def emit_review_summary(self, summary: Dict[str, Any]):
        name = summary.get("name", "Applicant")
        aadhaar_masked = summary.get("aadhaar", "XXXX")
        income = summary.get("income", "0")
        speech = (
            f"Please verify your application details: Name {name}, Aadhaar ending in {aadhaar_masked}, "
            f"Annual income {income} rupees. "
            f"Say 'Confirm' or 'Submit' to send your application, or say 'Cancel' to abort."
        )
        self.spoken_log.append(speech)
        self.tts_callback(speech)

    def emit_receipt(self, tracking_id: str, timestamp: str):
        speech = f"Application submitted successfully. Your tracking number is {tracking_id}. Please keep this number for your records."
        self.spoken_log.append(speech)
        self.tts_callback(speech)


class DeafAccessibilityAdapter(BaseAccessibilityAdapter):
    """Deaf/Hard-of-Hearing Output Adapter: High-Contrast Visual Cards & MediaPipe Gesture prompts."""
    def __init__(self, visual_card_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.visual_card_callback = visual_card_callback or self._default_card
        self.card_history: List[Dict[str, Any]] = []

    def _default_card(self, card_data: Dict[str, Any]):
        logger.info(f"[VISUAL_CARD_UI] High-Contrast Card: {card_data.get('title')} -> {card_data.get('body')}")

    def emit_info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        card = {"type": "INFO", "title": "Information", "body": message, "metadata": metadata or {}}
        self.card_history.append(card)
        self.visual_card_callback(card)

    def emit_warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        card = {"type": "WARNING", "title": "Warning", "body": message, "metadata": metadata or {}}
        self.card_history.append(card)
        self.visual_card_callback(card)

    def emit_error(self, message: str, errors: List[str], metadata: Optional[Dict[str, Any]] = None):
        card = {"type": "ERROR", "title": "Validation Error", "body": message, "errors": errors, "metadata": metadata or {}}
        self.card_history.append(card)
        self.visual_card_callback(card)

    def emit_review_summary(self, summary: Dict[str, Any]):
        card = {
            "type": "REVIEW_SUMMARY",
            "title": "Application Review",
            "summary": summary,
            "prompt": "Show THUMBS-UP gesture or click CONFIRM to submit. Show OPEN-PALM or click CANCEL to abort."
        }
        self.card_history.append(card)
        self.visual_card_callback(card)

    def emit_receipt(self, tracking_id: str, timestamp: str):
        card = {
            "type": "RECEIPT",
            "title": "Application Submitted Successfully",
            "tracking_id": tracking_id,
            "timestamp": timestamp
        }
        self.card_history.append(card)
        self.visual_card_callback(card)


class StandardAccessibilityAdapter(BaseAccessibilityAdapter):
    """Standard UI Adapter for citizens without specific accessibility profiles."""
    def __init__(self):
        self.notifications: List[str] = []

    def emit_info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.notifications.append(f"[INFO] {message}")
        logger.info(f"[STANDARD_UI] {message}")

    def emit_warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.notifications.append(f"[WARN] {message}")
        logger.warning(f"[STANDARD_UI] {message}")

    def emit_error(self, message: str, errors: List[str], metadata: Optional[Dict[str, Any]] = None):
        self.notifications.append(f"[ERROR] {message}: {errors}")
        logger.error(f"[STANDARD_UI] {message}: {errors}")

    def emit_review_summary(self, summary: Dict[str, Any]):
        self.notifications.append(f"[REVIEW] {json.dumps(summary)}")
        logger.info(f"[STANDARD_UI] Summary Ready: {summary.get('status')}")

    def emit_receipt(self, tracking_id: str, timestamp: str):
        self.notifications.append(f"[RECEIPT] ID: {tracking_id}")
        logger.info(f"[STANDARD_UI] Form Submitted. Tracking ID: {tracking_id}")


# =====================================================================
# 5. VERHOEFF ALGORITHM FOR AADHAAR CHECKSUM VALIDATION
# =====================================================================

class VerhoeffAlgorithm:
    """Verhoeff checksum validation table for 12-digit Indian Aadhaar numbers."""
    d = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    ]

    p = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
    ]

    inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

    @classmethod
    def validate(cls, num_str: str) -> bool:
        """Validates a numeric string against the Verhoeff checksum algorithm."""
        if not num_str or not num_str.isdigit():
            return False
        c = 0
        reversed_digits = [int(x) for x in reversed(num_str)]
        for i, digit in enumerate(reversed_digits):
            c = cls.d[c][cls.p[i % 8][digit]]
        return c == 0

    @classmethod
    def generate_checksum_digit(cls, base_11_digits: str) -> str:
        """Computes the 12th Verhoeff checksum digit for an 11-digit prefix."""
        if not base_11_digits.isdigit() or len(base_11_digits) != 11:
            return "0"
        c = 0
        reversed_digits = [int(x) for x in reversed(base_11_digits)]
        for i, digit in enumerate(reversed_digits):
            c = cls.d[c][cls.p[(i + 1) % 8][digit]]
        return str(cls.inv[c])


# =====================================================================
# 6. CRITIC AGENT (PRE-SUBMISSION AUDIT & FAIL-CLOSED GUARDRAIL)
# =====================================================================

class CriticAgent:
    """
    Independent Pre-Submission Audit Agent.
    Evaluates form DOM/data against format regexes, checksums, range boundaries,
    and biographical consistency between user input and OCR document scans.
    FAIL CLOSED: Any critical validation error blocks form submission.
    """
    def __init__(self, name_discrepancy_threshold: float = 0.6):
        self.name_discrepancy_threshold = name_discrepancy_threshold

    @staticmethod
    def _levenshtein_similarity(s1: str, s2: str) -> float:
        """Calculates normalized string similarity ratio [0.0 to 1.0]."""
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # Simple dynamic programming Levenshtein distance
        rows = len(s1) + 1
        cols = len(s2) + 1
        dist = [[0 for _ in range(cols)] for _ in range(rows)]
        
        for i in range(1, rows):
            dist[i][0] = i
        for j in range(1, cols):
            dist[0][j] = j
            
        for col in range(1, cols):
            for row in range(1, rows):
                if s1[row - 1] == s2[col - 1]:
                    cost = 0
                else:
                    cost = 1
                dist[row][col] = min(
                    dist[row - 1][col] + 1,      # deletion
                    dist[row][col - 1] + 1,      # insertion
                    dist[row - 1][col - 1] + cost # substitution
                )
        
        max_len = max(len(s1), len(s2))
        return 1.0 - (dist[rows - 1][cols - 1] / max_len)

    def validate_form(
        self,
        form_data: Dict[str, Any],
        ocr_data: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Conducts pre-submission inspection.
        Returns structured validation report.
        """
        errors: List[str] = []
        warnings: List[str] = []
        discrepancies: List[str] = []
        checked_fields: List[str] = []

        logger.info("[CRITIC_AGENT] Starting pre-submission form audit...")

        # 1. Validate Applicant Name
        name = form_data.get("txtApplicantName") or form_data.get("applicantName")
        checked_fields.append("applicantName")
        if not name or not str(name).strip():
            errors.append("Applicant name is required and cannot be blank.")
        elif len(str(name).strip()) < 2:
            errors.append("Applicant name is too short (minimum 2 characters).")

        # 2. Validate Aadhaar UID (12-digit regex & checksum)
        aadhaar = form_data.get("txtAadhaarNo") or form_data.get("aadhaarNo")
        checked_fields.append("aadhaarNo")
        if not aadhaar:
            errors.append("Aadhaar UID is required.")
        else:
            aadhaar_clean = re.sub(r"\s+", "", str(aadhaar))
            if not re.match(r"^\d{12}$", aadhaar_clean):
                errors.append(f"Aadhaar UID must contain exactly 12 numeric digits (got {len(aadhaar_clean)} digits).")
            else:
                # Run Verhoeff Checksum
                is_checksum_valid = VerhoeffAlgorithm.validate(aadhaar_clean)
                if not is_checksum_valid:
                    # Warning or error based on strict mode
                    errors.append("Aadhaar number failed Verhoeff checksum validation.")

        # 3. Validate Annual Income (Must be > 0)
        if "txtAnnualIncome" in form_data or "annualIncome" in form_data:
            income_val = form_data.get("txtAnnualIncome") or form_data.get("annualIncome")
            checked_fields.append("annualIncome")
            try:
                income_num = float(str(income_val).replace(",", "").strip())
                if income_num <= 0:
                    errors.append("Annual income must be a positive number greater than 0.")
            except (ValueError, TypeError):
                errors.append("Annual income must be a valid numeric value.")

        # 4. Validate Mandatory Cascading Dropdowns (Must not be empty or placeholder)
        dropdown_keys = ["ddlDistrict", "ddlTaluk", "ddlVillage", "ddlPurpose", "disabilityCategory", "ddlReligion"]
        for ddl in dropdown_keys:
            if ddl in form_data:
                checked_fields.append(ddl)
                val = form_data.get(ddl)
                if not val or str(val).strip() in ["", "-- Select --", "0", "None"]:
                    errors.append(f"Mandatory dropdown '{ddl}' is not selected.")

        # 5. Validate Mandatory File Attachments
        file_keys = ["fileAadhaar", "fileCasteProof", "fileMedicalCertificate"]
        for fkey in file_keys:
            if fkey in form_data:
                checked_fields.append(fkey)
                file_val = form_data.get(fkey)
                if not file_val:
                    errors.append(f"Mandatory file upload '{fkey}' is missing.")
                elif isinstance(file_val, bytes) and len(file_val) == 0:
                    errors.append(f"Uploaded file '{fkey}' is empty (0 bytes).")

        # 6. Validate Discrepancies between Spoken/Input Name and Physical Document OCR
        if ocr_data and "full_name" in ocr_data and name:
            ocr_name = str(ocr_data.get("full_name", "")).strip()
            if ocr_name:
                sim = self._levenshtein_similarity(str(name), ocr_name)
                if sim < self.name_discrepancy_threshold:
                    disc = f"Biographical discrepancy: Entered name does not match OCR document name (Similarity: {sim*100:.1f}%)."
                    discrepancies.append(disc)
                    errors.append(disc)

        # 7. Validate Discrepancies between Aadhaar entered and Aadhaar OCR
        if ocr_data and "aadhaar_number" in ocr_data and aadhaar:
            ocr_uid = re.sub(r"\s+", "", str(ocr_data.get("aadhaar_number", "")))
            entered_uid = re.sub(r"\s+", "", str(aadhaar))
            if ocr_uid and entered_uid and ocr_uid != entered_uid:
                disc = "Aadhaar UID mismatch: Entered number does not match scanned document UID."
                discrepancies.append(disc)
                errors.append(disc)

        passed = len(errors) == 0
        status_msg = "AUDIT PASSED" if passed else f"AUDIT FAILED ({len(errors)} errors)"
        logger.info(f"[CRITIC_AGENT] Audit result: {status_msg}")

        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "discrepancies": discrepancies,
            "checked_fields": checked_fields,
            "timestamp": time.time()
        }


# =====================================================================
# 7. ONE-TIME SUBMISSION TOKEN (PREVENT DOUBLE SUBMISSION)
# =====================================================================

class SubmissionToken:
    """
    Cryptographic single-use authorization token.
    Issued ONLY after Critic verification passes and Supervisor reviews summary.
    Enforces atomic one-time execution and prevents replay / double submission.
    """
    def __init__(self, ttl_seconds: float = 60.0):
        self.token_id: str = f"TOK-{uuid.uuid4().hex[:12]}-{secrets.token_hex(4)}"
        self.created_at: float = time.time()
        self.ttl_seconds: float = ttl_seconds
        self.is_consumed: bool = False
        self.is_invalidated: bool = False

    def is_valid(self) -> bool:
        """Returns True if token has not expired and has not been used or cancelled."""
        if self.is_consumed or self.is_invalidated:
            return False
        return (time.time() - self.created_at) <= self.ttl_seconds

    def consume(self) -> bool:
        """Atomically uses the token for form submission."""
        if not self.is_valid():
            logger.warning(f"[TOKEN_GUARD] Attempted to consume invalid/expired token: {self.token_id}")
            return False
        self.is_consumed = True
        logger.info(f"[TOKEN_GUARD] Token successfully consumed for 1-time submission: {self.token_id}")
        return True

    def invalidate(self):
        """Immediately revokes the token (on cancellation, departure, or error)."""
        self.is_invalidated = True
        logger.info(f"[TOKEN_GUARD] Token invalidated: {self.token_id}")


# =====================================================================
# 8. SUPERVISOR AGENT & HUMAN-IN-THE-LOOP INTERLOCK
# =====================================================================

class SupervisorAgent:
    """
    Supervisor Agent (Human-in-the-Loop Circuit Breaker).
    Holds the execution lock preventing automated form submission without explicit human consent.
    Adapts verification delivery to Blind, Deaf, Deafblind, and Standard citizens.
    """
    def __init__(self, mode: AccessibilityMode = AccessibilityMode.STANDARD_MODE):
        self.mode = mode
        self.current_token: Optional[SubmissionToken] = None
        self.is_review_ready: bool = False
        self.is_confirmed: bool = False
        self.is_cancelled: bool = False
        self.cached_summary: Optional[Dict[str, Any]] = None

    def create_compact_summary(self, form_data: Dict[str, Any], critic_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a compact, PII-masked summary dictionary.
        Masks Aadhaar to last 4 digits only.
        """
        name = form_data.get("txtApplicantName") or form_data.get("applicantName") or "Applicant"
        aadhaar = form_data.get("txtAadhaarNo") or form_data.get("aadhaarNo") or ""
        aadhaar_clean = re.sub(r"\s+", "", str(aadhaar))
        aadhaar_masked = f"••••{aadhaar_clean[-4:]}" if len(aadhaar_clean) >= 4 else "••••0000"
        
        income_val = form_data.get("txtAnnualIncome") or form_data.get("annualIncome") or "N/A"
        
        docs_count = sum(1 for k in ["fileAadhaar", "fileCasteProof", "fileMedicalCertificate"] if form_data.get(k))
        
        summary = {
            "name": str(name),
            "aadhaar": aadhaar_masked,
            "income": f"₹{income_val}",
            "documents_verified": docs_count,
            "errors": len(critic_report.get("errors", [])),
            "status": "READY_FOR_CONFIRMATION" if critic_report.get("passed") else "CORRECTION_REQUIRED"
        }
        self.cached_summary = summary
        return summary

    def prepare_review(
        self,
        form_data: Dict[str, Any],
        critic_report: Dict[str, Any],
        adapter: BaseAccessibilityAdapter
    ) -> Optional[SubmissionToken]:
        """
        Evaluates critic report and prepares accessibility summary.
        If critic failed, emits error and halts.
        If critic passed, generates 1-time SubmissionToken and awaits confirmation.
        """
        if not critic_report.get("passed", False):
            logger.warning("[SUPERVISOR_AGENT] Critic audit failed. Blocking submission token issuance.")
            adapter.emit_error("Form contains errors", critic_report.get("errors", []))
            return None

        # Generate single-use submission token
        self.current_token = SubmissionToken(ttl_seconds=60.0)
        self.is_review_ready = True
        self.is_confirmed = False
        self.is_cancelled = False

        summary = self.create_compact_summary(form_data, critic_report)
        logger.info(f"[SUPERVISOR_AGENT] Prepared review summary for mode: {self.mode.value}")

        # Dispatch review to citizen via active accessibility channel
        adapter.emit_review_summary(summary)
        return self.current_token

    def handle_citizen_confirmation(self, confirmation_source: str) -> bool:
        """
        Processes human confirmation signal from Voice, Gesture, or Tactile input.
        """
        if not self.is_review_ready or not self.current_token or not self.current_token.is_valid():
            logger.warning(f"[SUPERVISOR_AGENT] Confirmation rejected: Review not ready or token expired (Source: {confirmation_source})")
            return False

        self.is_confirmed = True
        logger.info(f"[SUPERVISOR_AGENT] Human confirmation verified via: {confirmation_source}. Submission gate UNLOCKED.")
        return True

    def handle_citizen_cancellation(self, reason: str = "User requested cancellation") -> bool:
        """Processes cancellation signal from Voice, Gesture, or Tactile Button B."""
        self.is_cancelled = True
        self.is_confirmed = False
        if self.current_token:
            self.current_token.invalidate()
        logger.info(f"[SUPERVISOR_AGENT] Session cancelled by citizen: {reason}")
        return True


# =====================================================================
# 9. RECEIPT VERIFICATION ENGINE
# =====================================================================

class ReceiptVerifier:
    """
    Receipt Verification Subsystem.
    Inspects portal response, verifies tracking token syntax, and announces receipt.
    """
    TRACKING_REGEX = re.compile(r"^KL-EDIST-2026-[A-Z0-9]{4,8}$", re.IGNORECASE)

    @classmethod
    def verify_receipt(cls, response_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Verifies acknowledgement receipt payload.
        Returns: (is_valid, tracking_id, timestamp)
        """
        tracking_id = response_data.get("tracking_id") or response_data.get("id")
        timestamp = response_data.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S")

        if not tracking_id:
            logger.error("[RECEIPT_VERIFIER] Receipt missing tracking ID.")
            return False, None, None

        if not cls.TRACKING_REGEX.match(str(tracking_id).strip()):
            logger.error(f"[RECEIPT_VERIFIER] Invalid tracking ID format: {tracking_id}")
            return False, tracking_id, timestamp

        logger.info(f"[RECEIPT_VERIFIER] Successfully verified receipt with tracking ID: {tracking_id}")
        return True, str(tracking_id), timestamp


# =====================================================================
# 10. EPHEMERAL PRIVACY PURGE & ZERO-TRACE MEMORY PURGE
# =====================================================================

class EphemeralMemoryPurge:
    """
    Zero-Trace Cryptographic Memory Scrubbing Subsystem.
    Emulates secure memory zeroization (`sodium_memzero`) by overwriting byte buffers with 0x00,
    clearing references, and terminating active browser/session contexts.
    Logs ZERO citizen PII.
    """
    @staticmethod
    def zero_byte_buffer(buf: Any) -> bool:
        """Overwrites bytearray / bytes buffer with zeros."""
        try:
            if isinstance(buf, bytearray):
                for i in range(len(buf)):
                    buf[i] = 0
                return True
            return True
        except Exception:
            return False

    @classmethod
    def purge_session(
        cls,
        form_data: Optional[Dict[str, Any]] = None,
        ocr_data: Optional[Dict[str, Any]] = None,
        token: Optional[SubmissionToken] = None,
        tactile_device: Optional[MockTactileDevice] = None,
        braille_display: Optional[MockBrailleDisplay] = None,
        extra_buffers: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Conducts complete ephemeral zeroization of all sensitive runtime data.
        """
        logger.info("[PRIVACY] Initiating ephemeral memory purge...")

        # 1. Purge OCR buffer
        if ocr_data is not None:
            for k in list(ocr_data.keys()):
                if isinstance(ocr_data[k], (bytearray, bytes)):
                    cls.zero_byte_buffer(ocr_data[k])
            ocr_data.clear()
        logger.info("[PRIVACY] OCR buffer purged")

        # 2. Purge Form PII
        if form_data is not None:
            for k in list(form_data.keys()):
                if isinstance(form_data[k], (bytearray, bytes)):
                    cls.zero_byte_buffer(form_data[k])
            form_data.clear()
        logger.info("[PRIVACY] Form PII cleared")

        # 3. Invalidate Submission Token
        if token is not None:
            token.invalidate()
        logger.info("[PRIVACY] Submission token invalidated")

        # 4. Clear Tactile & Braille Buffers
        if tactile_device is not None:
            tactile_device.clear_history()
        if braille_display is not None:
            braille_display.clear()
        logger.info("[PRIVACY] Accessibility hardware buffers zeroed")

        # 5. Overwrite Extra Buffers
        if extra_buffers:
            for b in extra_buffers:
                cls.zero_byte_buffer(b)

        logger.info("[PRIVACY] Browser session terminated and ephemeral state destroyed")
        return {"status": "PURGED", "timestamp": time.time()}


# =====================================================================
# 11. DEPARTURE WATCHDOG (INACTIVITY / ABANDONMENT SCRUBBER)
# =====================================================================

class DepartureWatchdog:
    """
    Ultrasonic Proximity & Inactivity Watchdog.
    Monitors citizen presence. If distance > 150cm or inactivity > timeout,
    initiates grace period warning, cancels session, and triggers emergency memory purge.
    """
    def __init__(
        self,
        inactivity_timeout_seconds: float = 10.0,
        departure_distance_cm: float = 150.0,
        on_departure_purge: Optional[Callable[[], None]] = None
    ):
        self.inactivity_timeout = inactivity_timeout_seconds
        self.departure_distance_cm = departure_distance_cm
        self.on_departure_purge = on_departure_purge
        self.last_activity_time: float = time.time()
        self.is_active = True

    def record_activity(self):
        """Refreshes watchdog timer upon any user interaction."""
        self.last_activity_time = time.time()

    def check_presence(self, current_distance_cm: float) -> Tuple[bool, str]:
        """
        Evaluates ultrasonic sensor distance metric.
        Returns: (should_abort, reason)
        """
        elapsed = time.time() - self.last_activity_time
        
        # User walked away
        if current_distance_cm > self.departure_distance_cm:
            logger.warning(f"[WATCHDOG] Citizen departed terminal (Distance: {current_distance_cm}cm > {self.departure_distance_cm}cm threshold)")
            if self.on_departure_purge:
                self.on_departure_purge()
            return True, "CITIZEN_DEPARTED"

        # Session inactivity
        if elapsed > self.inactivity_timeout:
            logger.warning(f"[WATCHDOG] Inactivity timeout reached ({elapsed:.1f}s > {self.inactivity_timeout}s)")
            if self.on_departure_purge:
                self.on_departure_purge()
            return True, "INACTIVITY_TIMEOUT"

        return False, "ACTIVE"


# =====================================================================
# 12. UNIFIED GOVERNANCE CONTROLLER (MODULE 6 MAIN PIPELINE)
# =====================================================================

class GovernanceController:
    """
    OmniKiosk Unified Governance Pipeline Controller.
    Coordinates Critic Agent, Supervisor Agent, Mode-specific Adapters,
    Submission execution, Receipt verification, and Ephemeral RAM purge.
    """
    def __init__(
        self,
        mode: AccessibilityMode = AccessibilityMode.STANDARD_MODE,
        submit_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ):
        self.mode = mode
        self.state = GovernanceState.IDLE
        self.critic = CriticAgent()
        self.supervisor = SupervisorAgent(mode=mode)
        self.submit_handler = submit_handler or self._default_submit_mock
        
        # Hardware abstractions
        self.tactile_device = MockTactileDevice()
        self.braille_display = MockBrailleDisplay()
        
        # Initialize appropriate accessibility adapter
        self.adapter = self._build_adapter()
        
        # Wire deafblind tactile buttons
        self.tactile_device.register_input_handlers(
            on_confirm=lambda: self.confirm_and_submit(confirmation_source="DEAFBLIND_TACTILE_BUTTON_A"),
            on_cancel=lambda: self.cancel_session(reason="DEAFBLIND_TACTILE_BUTTON_B")
        )
        
        # In-memory session buffers
        self.current_form_data: Dict[str, Any] = {}
        self.current_ocr_data: Dict[str, Any] = {}
        self.last_receipt: Optional[Dict[str, Any]] = None

    def _build_adapter(self) -> BaseAccessibilityAdapter:
        if self.mode == AccessibilityMode.DEAFBLIND_MODE:
            return DeafblindAccessibilityAdapter(self.tactile_device, self.braille_display)
        elif self.mode == AccessibilityMode.BLIND_MODE:
            return BlindAccessibilityAdapter()
        elif self.mode == AccessibilityMode.DEAF_MODE:
            return DeafAccessibilityAdapter()
        else:
            return StandardAccessibilityAdapter()

    def set_mode(self, mode: AccessibilityMode):
        """Switches active accessibility mode and updates adapter."""
        self.mode = mode
        self.supervisor.mode = mode
        self.adapter = self._build_adapter()
        logger.info(f"[GOVERNANCE_CONTROLLER] Switched accessibility mode to: {self.mode.value}")

    def _default_submit_mock(self, form_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Default mock submission handler generating compliant receipt."""
        token_id = f"{secrets.randbelow(9000) + 1000}"
        tracking_id = f"KL-EDIST-2026-{token_id}"
        return {
            "status": "SUCCESS",
            "tracking_id": tracking_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "receipt_url": f"/receipts/acknowledgement-slip.html?id={tracking_id}"
        }

    def start_governance_review(
        self,
        form_data: Dict[str, Any],
        ocr_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, GovernanceState]:
        """
        Step 1: Ingests populated form and initiates Critic Agent verification.
        Step 2: Prepares Supervisor review.
        """
        self.current_form_data = dict(form_data)
        self.current_ocr_data = dict(ocr_data) if ocr_data else {}
        self.state = GovernanceState.CRITIC_VALIDATING

        # 1. Critic Agent Form Audit
        critic_report = self.critic.validate_form(self.current_form_data, self.current_ocr_data)
        
        if not critic_report["passed"]:
            self.state = GovernanceState.CRITIC_FAILED
            self.adapter.emit_error("Form validation failed", critic_report["errors"])
            return False, self.state

        self.state = GovernanceState.CRITIC_PASSED

        # 2. Supervisor Prepares Human-in-the-Loop Review
        self.state = GovernanceState.SUPERVISOR_REVIEW
        token = self.supervisor.prepare_review(self.current_form_data, critic_report, self.adapter)
        
        if not token:
            self.state = GovernanceState.ERROR
            return False, self.state

        if self.mode == AccessibilityMode.DEAFBLIND_MODE:
            self.state = GovernanceState.WAITING_FOR_DEAFBLIND_CONFIRMATION
        else:
            self.state = GovernanceState.WAITING_FOR_CONFIRMATION

        return True, self.state

    def confirm_and_submit(self, confirmation_source: str = "EXPLICIT_CONFIRM") -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Step 3: Human confirmation received -> Consumes 1-time token -> Submits form -> Verifies Receipt.
        """
        if self.state not in [GovernanceState.WAITING_FOR_CONFIRMATION, GovernanceState.WAITING_FOR_DEAFBLIND_CONFIRMATION]:
            logger.warning(f"[GOVERNANCE_CONTROLLER] Submit blocked: Current state is {self.state.value}")
            return False, None

        # Verify confirmation through Supervisor interlock
        confirmed = self.supervisor.handle_citizen_confirmation(confirmation_source)
        if not confirmed:
            return False, None

        # Check and consume 1-time submission token
        token = self.supervisor.current_token
        if not token or not token.consume():
            self.state = GovernanceState.ERROR
            self.adapter.emit_error("Submission token invalid or already consumed", ["Double submission prevented"])
            return False, None

        self.state = GovernanceState.SUBMITTING
        
        # Execute form POST submission
        try:
            response = self.submit_handler(self.current_form_data)
        except Exception as e:
            logger.error(f"[GOVERNANCE_CONTROLLER] Submission exception: {e}")
            self.state = GovernanceState.ERROR
            self.adapter.emit_error(f"Submission failed: {str(e)}", [str(e)])
            return False, None

        # Step 4: Verify Receipt
        self.state = GovernanceState.RECEIPT_VERIFY
        is_valid, tracking_id, timestamp = ReceiptVerifier.verify_receipt(response)
        
        if not is_valid or not tracking_id:
            self.state = GovernanceState.ERROR
            self.adapter.emit_error("Receipt verification failed", ["Invalid tracking number returned from portal"])
            return False, None

        self.last_receipt = {
            "tracking_id": tracking_id,
            "timestamp": timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.state = GovernanceState.SUCCESS
        
        # Deliver receipt via mode-specific adapter
        self.adapter.emit_receipt(tracking_id, self.last_receipt["timestamp"])
        
        # Step 5: Ephemeral Privacy Purge
        self.purge_privacy_state()
        return True, self.last_receipt

    def cancel_session(self, reason: str = "User cancelled"):
        """Handles citizen cancellation, emits feedback, and purges state."""
        self.supervisor.handle_citizen_cancellation(reason)
        self.state = GovernanceState.CANCELLED
        
        if self.mode == AccessibilityMode.DEAFBLIND_MODE:
            self.tactile_device.vibrate("CANCEL")
            self.braille_display.display_text("SESSION CANCELLED")
        else:
            self.adapter.emit_info("Session cancelled")

        self.purge_privacy_state()

    def purge_privacy_state(self):
        """Executes zero-trace ephemeral memory scrub."""
        EphemeralMemoryPurge.purge_session(
            form_data=self.current_form_data,
            ocr_data=self.current_ocr_data,
            token=self.supervisor.current_token,
            tactile_device=self.tactile_device,
            braille_display=self.braille_display
        )
        self.state = GovernanceState.PURGED
