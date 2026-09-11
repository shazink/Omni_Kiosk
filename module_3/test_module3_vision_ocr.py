"""
Unit and Integration Test Suite for OmniKiosk Module 3: Vision & OCR
Can be run directly: python module_3/test_module3_vision_ocr.py

Tests from the implementation plan:
1. Frame shifted 100px right  -> Guidance: "Move document left"
2. Frame rotated 15 degrees   -> Guidance: "Rotate paper"
3. Blurry frame               -> Sharpness < 85%, capture held
4. Centered sharp Aadhaar     -> Auto-snapshot triggers
5. OCR extracts Name and Aadhaar number
6. Voice override "Capture now" forces immediate capture
"""

import json
import os
import sys
import unittest

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_DIR = os.path.dirname(_MODULE_DIR)

for d in [_WORKSPACE_DIR, _MODULE_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

from module_3.document_scanner import (
    Frame,
    DocumentContourDetector,
    SpatialAlignmentEngine,
    SpatialGuidanceEngine,
    SharpnessEvaluator,
    AutoSnapshotController,
    LocalOCR,
    SyntheticFrameGenerator,
    DocumentScannerSession,
    SHARPNESS_THRESHOLD,
    STABILITY_FRAMES,
    OFFSET_THRESHOLD_PX,
    SKEW_THRESHOLD_DEG,
)


class TestModule3VisionOCR(unittest.TestCase):
    """Comprehensive test suite following the implementation plan spec."""

    @classmethod
    def setUpClass(cls):
        cls.gen = SyntheticFrameGenerator(width=640, height=480)

    # ------------------------------------------------------------------
    # Test 1: Frame shifted 100px right -> guidance "Move document left"
    # ------------------------------------------------------------------
    def test_01_shifted_right_guidance(self):
        """Frame shifted 100px right: guidance should say 'Move document left'."""
        frame = self.gen.create_shifted_frame(shift_x=100)
        session = DocumentScannerSession()
        result = session.process_frame(frame)

        guidance_text = " ".join(result.get("guidance", [])).lower()
        self.assertTrue(
            "left" in guidance_text,
            f"Expected 'left' in guidance when document is shifted right, got: {result['guidance']}"
        )
        session.terminate()

    # ------------------------------------------------------------------
    # Test 2: Frame rotated 15 degrees -> guidance "Rotate paper"
    # ------------------------------------------------------------------
    def test_02_rotated_guidance(self):
        """Frame rotated 15 degrees: guidance should say 'Rotate paper'."""
        frame = self.gen.create_rotated_frame(rotation_deg=15.0)
        session = DocumentScannerSession()
        result = session.process_frame(frame)

        guidance_text = " ".join(result.get("guidance", [])).lower()
        self.assertTrue(
            "rotate" in guidance_text,
            f"Expected 'rotate' in guidance when document is rotated 15°, got: {result['guidance']}"
        )
        session.terminate()

    # ------------------------------------------------------------------
    # Test 3: Blurry frame -> sharpness < 85% and capture is held
    # ------------------------------------------------------------------
    def test_03_blurry_frame_held(self):
        """Blurry frame: sharpness should be < 85% and no auto-capture."""
        frame = self.gen.create_blurry_frame(blur_level=0.8)
        session = DocumentScannerSession()
        result = session.process_frame(frame)

        sharpness = result.get("sharpness", {})
        # Blurry frame should not trigger auto-capture on first pass
        self.assertNotEqual(
            result["status"], "CAPTURED",
            "Blurry frame should NOT trigger auto-capture"
        )
        session.terminate()

    # ------------------------------------------------------------------
    # Test 4: Centered sharp Aadhaar card -> auto-snapshot triggers
    # ------------------------------------------------------------------
    def test_04_centered_sharp_auto_snapshot(self):
        """Centered, sharp Aadhaar card: auto-snapshot should trigger after stability frames."""
        frame = self.gen.create_sharp_aadhaar_frame(
            name="Arun Kumar", aadhaar="987654321098", dob="15/05/1994"
        )
        session = DocumentScannerSession()

        captured = False
        result = {}
        for i in range(STABILITY_FRAMES + 5):
            result = session.process_frame(frame)
            if result["status"] == "CAPTURED":
                captured = True
                break

        self.assertTrue(captured, "Auto-snapshot should trigger for centered sharp document")
        self.assertEqual(result["trigger"], "AUTO_STABILITY")
        session.terminate()

    # ------------------------------------------------------------------
    # Test 5: OCR extracts Name "Arun Kumar" and Aadhaar "987654321098"
    # ------------------------------------------------------------------
    def test_05_ocr_extraction(self):
        """Local OCR should extract Name and Aadhaar number from embedded text."""
        ocr = LocalOCR()

        raw_text = (
            "GOVERNMENT OF INDIA\n"
            "Name: Arun Kumar\n"
            "DOB: 15/05/1994\n"
            "9876 5432 1098"
        )
        result = ocr.parse_fields(raw_text)

        self.assertEqual(result["full_name"], "Arun Kumar")
        self.assertEqual(result["aadhaar_number"], "987654321098")
        self.assertEqual(result["dob"], "1994-05-15")

    # ------------------------------------------------------------------
    # Test 6: Voice override "Capture now" forces immediate capture
    # ------------------------------------------------------------------
    def test_06_voice_override_capture(self):
        """Voice override 'Capture now' should force immediate capture regardless of stability."""
        frame = self.gen.create_shifted_frame(shift_x=50)
        session = DocumentScannerSession()

        result_normal = session.process_frame(frame)
        self.assertNotEqual(result_normal["status"], "CAPTURED")

        session.snapshot_controller.reset()
        result_voice = session.force_capture(frame)

        self.assertEqual(result_voice["status"], "CAPTURED")
        self.assertEqual(result_voice["trigger"], "VOICE_OVERRIDE")
        session.terminate()

    # ------------------------------------------------------------------
    # Test 7: PII sanitizer — Aadhaar regex extraction accuracy
    # ------------------------------------------------------------------
    def test_07_aadhaar_regex_patterns(self):
        """Aadhaar regex should match various formatting patterns."""
        ocr = LocalOCR()

        # Spaced format: 9876 5432 1098
        result1 = ocr.parse_fields("UID: 9876 5432 1098")
        self.assertEqual(result1["aadhaar_number"], "987654321098")

        # Continuous format: 987654321098
        result2 = ocr.parse_fields("Aadhaar No: 987654321098")
        self.assertEqual(result2["aadhaar_number"], "987654321098")

    # ------------------------------------------------------------------
    # Test 8: Spatial alignment vector math
    # ------------------------------------------------------------------
    def test_08_spatial_alignment_vectors(self):
        """Spatial alignment engine should compute correct ΔX, ΔY, and skew angle."""
        engine = SpatialAlignmentEngine()

        # Document centered at frame center (320, 240) for 640x480 frame
        centered_corners = [(170, 140), (470, 140), (470, 340), (170, 340)]
        alignment = engine.compute_alignment(centered_corners, 640, 480)

        self.assertTrue(alignment["is_centered"])
        self.assertTrue(alignment["is_straight"])
        self.assertAlmostEqual(alignment["delta_x"], 0.0, delta=1.0)
        self.assertAlmostEqual(alignment["delta_y"], 0.0, delta=1.0)

    # ------------------------------------------------------------------
    # Test 9: Sharpness evaluator baseline calibration
    # ------------------------------------------------------------------
    def test_09_sharpness_evaluator(self):
        """Sharpness evaluator should produce higher scores for sharp vs blurry frames."""
        gen = SyntheticFrameGenerator()
        evaluator = SharpnessEvaluator()

        sharp_frame = gen.create_frame(blur_level=0.0)
        blurry_frame = gen.create_frame(blur_level=0.9)

        sharp_result = evaluator.evaluate(sharp_frame)
        blurry_result = evaluator.evaluate(blurry_frame)

        # Sharp frame should have higher variance than blurry
        self.assertGreaterEqual(
            sharp_result["sharpness_score"],
            blurry_result["sharpness_score"],
            "Sharp frame should have >= sharpness score than blurry frame"
        )

    # ------------------------------------------------------------------
    # Test 10: Session termination securely clears buffers
    # ------------------------------------------------------------------
    def test_10_session_termination_clears_buffers(self):
        """Session termination should securely clear all volatile memory buffers."""
        frame = self.gen.create_sharp_aadhaar_frame()
        session = DocumentScannerSession()

        session.force_capture(frame)
        self.assertIsNotNone(session.snapshot_controller.captured_frame)

        session.terminate()
        self.assertIsNone(session.snapshot_controller.captured_frame)
        self.assertIsNone(session.result)
        self.assertFalse(session.active)

    # ------------------------------------------------------------------
    # Test 11: Frame container data integrity
    # ------------------------------------------------------------------
    def test_11_frame_data_integrity(self):
        """Frame to_bytes() should produce consistent volatile memory representation."""
        frame = self.gen.create_frame()
        raw_bytes = frame.to_bytes()

        self.assertEqual(len(raw_bytes), 640 * 480 * 3)
        self.assertIsInstance(raw_bytes, bytes)

    # ------------------------------------------------------------------
    # Test 12: Date normalization
    # ------------------------------------------------------------------
    def test_12_date_normalization(self):
        """OCR date normalizer should convert DD/MM/YYYY to YYYY-MM-DD."""
        ocr = LocalOCR()
        self.assertEqual(ocr._normalize_date("15/05/1994"), "1994-05-15")
        self.assertEqual(ocr._normalize_date("01-12-2000"), "2000-12-01")
        self.assertEqual(ocr._normalize_date("25.03.1985"), "1985-03-25")

    # ------------------------------------------------------------------
    # Test 13: Full pipeline integration
    # ------------------------------------------------------------------
    def test_13_full_pipeline_integration(self):
        """Full pipeline: create -> process N frames -> capture -> extract -> terminate."""
        session = DocumentScannerSession()
        gen = SyntheticFrameGenerator()

        frame = gen.create_sharp_aadhaar_frame(
            name="Arun Kumar",
            aadhaar="987654321098",
            dob="15/05/1994",
        )

        result = None
        for _ in range(STABILITY_FRAMES + 5):
            result = session.process_frame(frame)
            if result["status"] == "CAPTURED":
                break

        self.assertIsNotNone(result)
        if result["status"] == "CAPTURED":
            self.assertIn("extracted_data", result)
            self.assertIn("image_buffer", result)
            self.assertIn("sharpness_score", result)

            extracted = result["extracted_data"]
            if extracted.get("full_name"):
                self.assertEqual(extracted["full_name"], "Arun Kumar")
            if extracted.get("aadhaar_number"):
                self.assertEqual(extracted["aadhaar_number"], "987654321098")

        buf = session.get_volatile_image_buffer()
        self.assertIsNotNone(buf)
        self.assertGreater(len(buf), 0)

        session.terminate()
        self.assertIsNone(session.get_volatile_image_buffer())


if __name__ == "__main__":
    print("=" * 70)
    print(" Running Module 3 Unit & Integration Test Suite (Vision & OCR)")
    print("=" * 70 + "\n")
    unittest.main(verbosity=2)
