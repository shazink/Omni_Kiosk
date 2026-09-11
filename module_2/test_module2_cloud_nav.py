"""
Unit and Integration Test Suite for OmniKiosk Module 2
Can be run directly: python module_2/test_module2_cloud_nav.py
"""

import json
import os
import sys
import unittest
import urllib.request

# Ensure workspace root and module_2 are in sys.path
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_DIR = os.path.dirname(_MODULE_DIR)

for d in [_WORKSPACE_DIR, _MODULE_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

from mock_edistrict.server import start_server_background
from module_2.cloud_navigator import (
    ServiceIntentClassifier,
    PIISanitizer,
    DoubtClearingEngine,
    BrowserInspector,
    CloudNavigatorSession,
    PORTAL_BASE_URL,
    SCHEMA_OUTPUT_PATH,
    DOWNLOADS_DIR
)


class TestModule2CloudNavigator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_started = False
        cls.httpd = None
        try:
            with urllib.request.urlopen(f"{PORTAL_BASE_URL}/healthz", timeout=1):
                pass
        except Exception:
            port = int(PORTAL_BASE_URL.split(":")[-1])
            cls.httpd, cls.thread = start_server_background(port)
            cls.server_started = True

    @classmethod
    def tearDownClass(cls):
        if cls.server_started and cls.httpd:
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def test_01_intent_classification(self):
        """Test 1: Intent classifier correctly maps natural queries to service URLs."""
        classifier = ServiceIntentClassifier(PORTAL_BASE_URL)

        queries = [
            ("I need an income certificate for college", "Income Certificate", "/forms/income-certificate.html"),
            ("I need proof of my annual income for scholarship", "Income Certificate", "/forms/income-certificate.html"),
            ("I want to apply for a disability pension", "Disability Pension", "/forms/disability-pension.html"),
            ("I need a community certificate for reservation", "Community Certificate", "/forms/community-certificate.html")
        ]

        for query, expected_name, expected_path in queries:
            result = classifier.classify(query)
            self.assertEqual(result["status"], "SUCCESS", f"Failed to classify: {query}")
            self.assertEqual(result["service_name"], expected_name)
            self.assertTrue(result["form_url"].endswith(expected_path))

    def test_02_playwright_portal_navigation(self):
        """Test 2: Browser navigator successfully connects to portal URL."""
        inspector = BrowserInspector()
        target_url = f"{PORTAL_BASE_URL}/forms/income-certificate.html"
        schema = inspector.inspect_form(target_url, "Income Certificate")
        self.assertIsNotNone(schema)
        self.assertEqual(schema["service_name"], "Income Certificate")
        self.assertEqual(schema["form_url"], target_url)
        inspector.close()

    def test_03_dom_schema_extraction(self):
        """Test 3: Live DOM extractor extracts all required fields and attributes."""
        inspector = BrowserInspector()
        target_url = f"{PORTAL_BASE_URL}/forms/income-certificate.html"
        schema = inspector.inspect_form(target_url, "Income Certificate")

        field_ids = [f["id"] for f in schema["fields"]]
        expected_ids = [
            "txtApplicantName",
            "txtAadhaarNo",
            "ddlDistrict",
            "ddlTaluk",
            "ddlVillage",
            "txtRationCardNo",
            "txtAnnualIncome",
            "ddlPurpose",
            "fileAadhaar"
        ]

        for expected in expected_ids:
            self.assertIn(expected, field_ids, f"Required field ID '{expected}' missing from schema")

        fields_by_id = {f["id"]: f for f in schema["fields"]}
        self.assertEqual(fields_by_id["txtApplicantName"]["type"], "text")
        self.assertTrue(fields_by_id["txtApplicantName"]["required"])
        self.assertEqual(fields_by_id["txtAadhaarNo"]["pattern"], "[0-9]{12}")
        self.assertTrue(fields_by_id["txtAadhaarNo"]["required"])
        self.assertEqual(fields_by_id["txtAnnualIncome"]["type"], "number")
        self.assertEqual(fields_by_id["txtAnnualIncome"]["min"], "1")
        self.assertIn(".pdf", fields_by_id["fileAadhaar"]["accept"])
        self.assertTrue(fields_by_id["fileAadhaar"]["required"])
        self.assertEqual(fields_by_id["ddlDistrict"]["type"], "select")
        self.assertIn("Thiruvananthapuram", fields_by_id["ddlDistrict"]["options"])

        inspector.close()

    def test_04_pro_forma_discovery_and_download(self):
        """Test 4: Pro-forma downloader discovers and downloads self-declaration affidavit."""
        inspector = BrowserInspector()
        target_url = f"{PORTAL_BASE_URL}/forms/income-certificate.html"
        schema = inspector.inspect_form(target_url, "Income Certificate")

        downloaded_docs = schema.get("downloaded_docs", [])
        self.assertTrue(len(downloaded_docs) > 0, "No pro-forma documents downloaded")
        affidavit_doc = downloaded_docs[0]
        self.assertTrue(affidavit_doc.endswith("self-declaration-affidavit.pdf"))
        self.assertTrue(os.path.exists(affidavit_doc), f"File {affidavit_doc} does not exist on disk")
        self.assertGreater(os.path.getsize(affidavit_doc), 0, "Downloaded PDF is empty")

        inspector.close()

    def test_05_kb_doubt_clearing_rag(self):
        """Test 5: Doubt clearing answers questions in plain language <= 2 sentences."""
        engine = DoubtClearingEngine()

        q = "What counts as annual income?"
        answer = engine.answer_question(q)
        self.assertIsNotNone(answer)
        sentences = [s.strip() for s in answer.split(".") if s.strip()]
        self.assertLessEqual(len(sentences), 2, f"Answer exceeds 2 sentences: {answer}")

        q2 = "How long does an income certificate take?"
        answer2 = engine.answer_question(q2)
        sentences2 = [s.strip() for s in answer2.split(".") if s.strip()]
        self.assertLessEqual(len(sentences2), 2)

    def test_06_pii_sanitizer(self):
        """Test 6: PII sanitizer scrubs Aadhaar, phone numbers, and emails."""
        raw_query = "My Aadhaar is 987654321098, phone is 9876543210, and email is citizen@kerala.gov.in. What documents do I need?"
        sanitized, was_redacted = PIISanitizer.sanitize(raw_query)

        self.assertTrue(was_redacted)
        self.assertNotIn("987654321098", sanitized)
        self.assertNotIn("9876543210", sanitized)
        self.assertNotIn("citizen@kerala.gov.in", sanitized)
        self.assertIn("[REDACTED_AADHAAR]", sanitized)
        self.assertIn("[REDACTED_PHONE]", sanitized)
        self.assertIn("[REDACTED_EMAIL]", sanitized)

    def test_07_handoff_and_schema_generation(self):
        """Test 7: Handoff trigger writes current_form_schema.json and terminates cloud session."""
        session = CloudNavigatorSession(PORTAL_BASE_URL)
        session.resolve_intent("I need an income certificate for college admission")
        
        handoff_result = session.check_handoff("Let's start filling")
        self.assertIsNotNone(handoff_result)
        self.assertEqual(handoff_result["status"], "HANDOFF_READY")
        self.assertTrue(handoff_result["cloud_session_closed"])

        self.assertTrue(os.path.exists(SCHEMA_OUTPUT_PATH))
        with open(SCHEMA_OUTPUT_PATH, "r", encoding="utf-8") as f:
            saved_schema = json.load(f)

        self.assertEqual(saved_schema["service_name"], "Income Certificate")
        self.assertTrue(len(saved_schema["fields"]) >= 9)
        self.assertTrue(len(saved_schema["downloaded_docs"]) >= 1)


if __name__ == "__main__":
    print("======================================================================")
    print(" Running Module 2 Unit & Integration Test Suite")
    print("======================================================================\n")
    unittest.main(verbosity=2)
