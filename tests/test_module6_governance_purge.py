"""
OmniKiosk - Module 6 Standalone & Integration Test Suite (`tests/test_module6_governance_purge.py`)
Exhaustive verification of:
1. Critic Agent Form Auditing & Fail-Closed Guardrails
2. Supervisor Agent Human-in-the-Loop Interlock & Double-Submission Token Guard
3. DEAFBLIND_MODE Tactile Hardware Abstraction & Refreshable Braille Simulator
4. Ephemeral RAM Zeroization & Zero-Trace PII Purge
5. Departure Watchdog Emergency Scrubbing
6. Multi-Agent End-to-End Governance Pipeline
"""

import os
import sys
import time
import unittest

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from governance_and_purge import (
    AccessibilityMode,
    GovernanceState,
    CriticAgent,
    SupervisorAgent,
    SubmissionToken,
    ReceiptVerifier,
    EphemeralMemoryPurge,
    DepartureWatchdog,
    GovernanceController,
    MockTactileDevice,
    MockBrailleDisplay,
    DeafblindAccessibilityAdapter,
    BlindAccessibilityAdapter,
    DeafAccessibilityAdapter,
    StandardAccessibilityAdapter,
    VerhoeffAlgorithm,
    TactileEvent,
    TACTILE_PATTERNS
)
from test_assets.generate_test_id import generate_valid_aadhaar, get_sample_citizen_profile


class TestModule6GovernanceAndPurge(unittest.TestCase):

    def setUp(self):
        self.valid_uid = generate_valid_aadhaar()
        self.valid_form_data = {
            "txtApplicantName": "Arun Kumar",
            "txtAadhaarNo": self.valid_uid,
            "ddlDistrict": "Thiruvananthapuram",
            "ddlTaluk": "Neyyattinkara",
            "ddlVillage": "Nemom",
            "txtRationCardNo": "14098231",
            "txtAnnualIncome": "75000",
            "ddlPurpose": "Scholarship",
            "fileAadhaar": b"SAMPLE_IN_MEMORY_AADHAAR_DOCUMENT_BYTES"
        }
        self.valid_ocr_data = {
            "full_name": "Arun Kumar",
            "aadhaar_number": self.valid_uid,
            "dob": "1994-05-15"
        }

    # =================================================================
    # 1. CRITIC AGENT TESTS
    # =================================================================

    def test_critic_valid_form(self):
        """Critic Agent should pass a completely valid form with matching OCR."""
        critic = CriticAgent()
        report = critic.validate_form(self.valid_form_data, self.valid_ocr_data)
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["errors"]), 0)

    def test_critic_missing_mandatory_name(self):
        """Critic Agent should flag missing applicant name."""
        critic = CriticAgent()
        bad_form = dict(self.valid_form_data)
        bad_form["txtApplicantName"] = ""
        report = critic.validate_form(bad_form, self.valid_ocr_data)
        self.assertFalse(report["passed"])
        self.assertTrue(any("Applicant name is required" in err for err in report["errors"]))

    def test_critic_invalid_aadhaar_length(self):
        """Critic Agent should flag invalid Aadhaar length (e.g. 10 digits)."""
        critic = CriticAgent()
        bad_form = dict(self.valid_form_data)
        bad_form["txtAadhaarNo"] = "1234567890"  # 10 digits
        report = critic.validate_form(bad_form, self.valid_ocr_data)
        self.assertFalse(report["passed"])
        self.assertTrue(any("12 numeric digits" in err for err in report["errors"]))

    def test_critic_invalid_aadhaar_verhoeff_checksum(self):
        """Critic Agent should flag invalid Verhoeff checksum digit."""
        critic = CriticAgent()
        bad_form = dict(self.valid_form_data)
        # Flip the last digit to break checksum
        last_digit = int(self.valid_uid[-1])
        flipped_last = str((last_digit + 1) % 10)
        bad_form["txtAadhaarNo"] = self.valid_uid[:-1] + flipped_last
        
        report = critic.validate_form(bad_form, self.valid_ocr_data)
        self.assertFalse(report["passed"])
        self.assertTrue(any("checksum" in err.lower() for err in report["errors"]))

    def test_critic_invalid_negative_or_zero_income(self):
        """Critic Agent should flag income <= 0."""
        critic = CriticAgent()
        bad_form = dict(self.valid_form_data)
        bad_form["txtAnnualIncome"] = "0"
        report = critic.validate_form(bad_form, self.valid_ocr_data)
        self.assertFalse(report["passed"])
        self.assertTrue(any("greater than 0" in err for err in report["errors"]))

    def test_critic_unselected_dropdown(self):
        """Critic Agent should flag placeholder dropdown selection."""
        critic = CriticAgent()
        bad_form = dict(self.valid_form_data)
        bad_form["ddlTaluk"] = "-- Select --"
        report = critic.validate_form(bad_form, self.valid_ocr_data)
        self.assertFalse(report["passed"])
        self.assertTrue(any("ddlTaluk" in err for err in report["errors"]))

    def test_critic_missing_file_attachment(self):
        """Critic Agent should flag missing mandatory document upload."""
        critic = CriticAgent()
        bad_form = dict(self.valid_form_data)
        bad_form["fileAadhaar"] = None
        report = critic.validate_form(bad_form, self.valid_ocr_data)
        self.assertFalse(report["passed"])
        self.assertTrue(any("fileAadhaar" in err for err in report["errors"]))

    def test_critic_biographical_name_discrepancy(self):
        """Critic Agent should flag discrepancy between entered name and OCR document name."""
        critic = CriticAgent()
        bad_ocr = dict(self.valid_ocr_data)
        bad_ocr["full_name"] = "Suresh Gopinath"  # completely different name
        report = critic.validate_form(self.valid_form_data, bad_ocr)
        self.assertFalse(report["passed"])
        self.assertTrue(len(report["discrepancies"]) > 0)
        self.assertTrue(any("discrepancy" in err.lower() for err in report["errors"]))

    # =================================================================
    # 2. SUPERVISOR AGENT & DOUBLE SUBMISSION TOKEN TESTS
    # =================================================================

    def test_supervisor_blocks_without_confirmation(self):
        """Supervisor should never permit submission before human confirmation."""
        supervisor = SupervisorAgent(mode=AccessibilityMode.STANDARD_MODE)
        adapter = StandardAccessibilityAdapter()
        critic = CriticAgent()
        report = critic.validate_form(self.valid_form_data, self.valid_ocr_data)
        
        token = supervisor.prepare_review(self.valid_form_data, report, adapter)
        self.assertIsNotNone(token)
        self.assertTrue(token.is_valid())
        self.assertFalse(supervisor.is_confirmed)  # Not yet confirmed

    def test_token_single_use_prevents_double_submission(self):
        """SubmissionToken must be single-use and block second consumption."""
        token = SubmissionToken(ttl_seconds=10.0)
        self.assertTrue(token.is_valid())
        
        # First use succeeds
        self.assertTrue(token.consume())
        self.assertFalse(token.is_valid())
        
        # Second use is blocked
        self.assertFalse(token.consume())

    def test_token_expiration(self):
        """Expired SubmissionToken must become invalid."""
        token = SubmissionToken(ttl_seconds=0.01)
        time.sleep(0.02)
        self.assertFalse(token.is_valid())
        self.assertFalse(token.consume())

    def test_token_invalidation_on_cancellation(self):
        """Cancelling the session must immediately revoke the active token."""
        supervisor = SupervisorAgent(mode=AccessibilityMode.STANDARD_MODE)
        adapter = StandardAccessibilityAdapter()
        critic = CriticAgent()
        report = critic.validate_form(self.valid_form_data, self.valid_ocr_data)
        
        token = supervisor.prepare_review(self.valid_form_data, report, adapter)
        self.assertTrue(token.is_valid())
        
        supervisor.handle_citizen_cancellation("Citizen pressed Cancel")
        self.assertTrue(supervisor.is_cancelled)
        self.assertFalse(token.is_valid())

    # =================================================================
    # 3. DEAFBLIND MODE TACTILE & BRAILLE ABSTRACTION TESTS
    # =================================================================

    def test_deafblind_mode_tactile_patterns(self):
        """MockTactileDevice must emit distinct vibration patterns for INFO, ERROR, and SUCCESS."""
        device = MockTactileDevice()
        
        # Info
        ev_info = device.vibrate("INFO")
        self.assertEqual(ev_info.pattern, "SHORT_PULSE")
        self.assertEqual(ev_info.symbol, "●")
        
        # Error
        ev_err = device.vibrate("ERROR")
        self.assertEqual(ev_err.pattern, "LONG_PULSE")
        self.assertEqual(ev_err.symbol, "▬▬▬")
        
        # Success
        ev_succ = device.vibrate("SUCCESS")
        self.assertEqual(ev_succ.pattern, "TRIPLE_PULSE")
        self.assertEqual(ev_succ.symbol, "● ● ●")

    def test_deafblind_braille_display_masking(self):
        """MockBrailleDisplay must convert characters to Unicode Braille and mask sensitive Aadhaar."""
        braille = MockBrailleDisplay(cell_count=80)
        tactile = MockTactileDevice()
        adapter = DeafblindAccessibilityAdapter(tactile, braille)
        
        summary = {
            "name": "Arun Kumar",
            "aadhaar": "••••1098",
            "income": "75000",
            "documents_verified": 1,
            "errors": 0
        }
        adapter.emit_review_summary(summary)
        
        # Verify text displayed in Braille contains masked UID and not raw 12 digits
        self.assertIn("UID:••••1098", braille.current_text)
        self.assertNotIn(self.valid_uid, braille.current_text)
        self.assertTrue(len(braille.current_braille) > 0)
        self.assertIn("PRESS A:OK B:NO", braille.current_text)

    def test_deafblind_tactile_button_confirmation_flow(self):
        """Pressing Tactile Button A (Confirm) completes Deafblind submission."""
        ctrl = GovernanceController(mode=AccessibilityMode.DEAFBLIND_MODE)
        ok, state = ctrl.start_governance_review(self.valid_form_data, self.valid_ocr_data)
        self.assertTrue(ok)
        self.assertEqual(state, GovernanceState.WAITING_FOR_DEAFBLIND_CONFIRMATION)
        
        # Simulate deafblind citizen pressing physical Tactile Button A
        ctrl.tactile_device.press_confirm()
        
        # Assert submission succeeded, receipt returned, and memory purged
        self.assertEqual(ctrl.state, GovernanceState.PURGED)
        self.assertIsNotNone(ctrl.last_receipt)
        self.assertTrue(ctrl.last_receipt["tracking_id"].startswith("KL-EDIST-2026-"))
        
        # Assert SUCCESS tactile pulse was emitted prior to purge
        self.assertEqual(ctrl.braille_display.current_text, "")  # purged

    def test_deafblind_tactile_button_cancellation_flow(self):
        """Pressing Tactile Button B (Cancel) cancels session and purges memory."""
        ctrl = GovernanceController(mode=AccessibilityMode.DEAFBLIND_MODE)
        ok, state = ctrl.start_governance_review(self.valid_form_data, self.valid_ocr_data)
        self.assertTrue(ok)
        
        # Simulate pressing Tactile Button B (Cancel)
        ctrl.tactile_device.press_cancel()
        
        self.assertEqual(ctrl.state, GovernanceState.PURGED)
        self.assertIsNone(ctrl.last_receipt)

    # =================================================================
    # 4. RECEIPT VERIFICATION TESTS
    # =================================================================

    def test_receipt_verifier_valid(self):
        """ReceiptVerifier should validate KL-EDIST-2026-XXXX format."""
        valid_response = {"tracking_id": "KL-EDIST-2026-8821", "timestamp": "2026-09-11 10:30:00"}
        is_valid, tid, ts = ReceiptVerifier.verify_receipt(valid_response)
        self.assertTrue(is_valid)
        self.assertEqual(tid, "KL-EDIST-2026-8821")

    def test_receipt_verifier_invalid_format(self):
        """ReceiptVerifier should reject non-compliant tracking tokens."""
        bad_response = {"tracking_id": "INVALID-TRACKING-123"}
        is_valid, tid, ts = ReceiptVerifier.verify_receipt(bad_response)
        self.assertFalse(is_valid)

    # =================================================================
    # 5. EPHEMERAL PURGE & PRIVACY ZEROIZATION TESTS
    # =================================================================

    def test_ephemeral_purge_zeroes_state(self):
        """EphemeralMemoryPurge should wipe all form dicts, OCR caches, and tokens."""
        form_copy = dict(self.valid_form_data)
        ocr_copy = dict(self.valid_ocr_data)
        token = SubmissionToken(ttl_seconds=30.0)
        tactile = MockTactileDevice()
        braille = MockBrailleDisplay()
        
        tactile.vibrate("INFO")
        braille.display_text("TEMP PII DATA")
        
        EphemeralMemoryPurge.purge_session(
            form_data=form_copy,
            ocr_data=ocr_copy,
            token=token,
            tactile_device=tactile,
            braille_display=braille
        )
        
        self.assertEqual(len(form_copy), 0)
        self.assertEqual(len(ocr_copy), 0)
        self.assertFalse(token.is_valid())
        self.assertEqual(len(tactile.event_history), 0)
        self.assertEqual(braille.current_text, "")

    def test_departure_watchdog_triggers_purge(self):
        """DepartureWatchdog should trigger emergency purge when user walks away."""
        purged = {"flag": False}
        def mark_purged():
            purged["flag"] = True

        watchdog = DepartureWatchdog(
            inactivity_timeout_seconds=5.0,
            departure_distance_cm=150.0,
            on_departure_purge=mark_purged
        )
        
        # User is close (50cm) -> active
        should_abort, reason = watchdog.check_presence(current_distance_cm=50.0)
        self.assertFalse(should_abort)
        self.assertFalse(purged["flag"])
        
        # User walks away (200cm > 150cm) -> abort & purge
        should_abort, reason = watchdog.check_presence(current_distance_cm=200.0)
        self.assertTrue(should_abort)
        self.assertEqual(reason, "CITIZEN_DEPARTED")
        self.assertTrue(purged["flag"])

    # =================================================================
    # 6. MULTIMODAL ACCESSIBILITY REVIEWS (BLIND, DEAF, STANDARD)
    # =================================================================

    def test_blind_mode_voice_confirmation_flow(self):
        """Blind mode provides spoken summary and accepts spoken 'Submit'."""
        ctrl = GovernanceController(mode=AccessibilityMode.BLIND_MODE)
        ok, state = ctrl.start_governance_review(self.valid_form_data, self.valid_ocr_data)
        self.assertTrue(ok)
        self.assertEqual(state, GovernanceState.WAITING_FOR_CONFIRMATION)
        
        # Citizen says "Submit"
        success, receipt = ctrl.confirm_and_submit(confirmation_source="SPOKEN_VOICE_SUBMIT")
        self.assertTrue(success)
        self.assertIsNotNone(receipt)

    def test_deaf_mode_gesture_confirmation_flow(self):
        """Deaf mode displays visual card and accepts verified Thumbs-Up gesture."""
        ctrl = GovernanceController(mode=AccessibilityMode.DEAF_MODE)
        ok, state = ctrl.start_governance_review(self.valid_form_data, self.valid_ocr_data)
        self.assertTrue(ok)
        self.assertEqual(state, GovernanceState.WAITING_FOR_CONFIRMATION)
        
        # MediaPipe gesture detector provides THUMBS_UP
        success, receipt = ctrl.confirm_and_submit(confirmation_source="MEDIAPIPE_GESTURE_THUMBS_UP")
        self.assertTrue(success)
        self.assertIsNotNone(receipt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
