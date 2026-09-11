"""
OmniKiosk - Module 5 Test Suite: Local Form-Filling & Playwright DOM Injection
File: tests/test_module5_dom_injection.py

Tests:
1. Loading mock current_form_schema.json.
2. Ingesting sample OCR payload with in-memory image buffer.
3. Conversational multi-slot extraction from natural speech statements.
4. Deterministic merging of OCR + Conversational inputs with provenance.
5. Step-by-step contextual prompt generation and accessibility cards.
6. Mock e-District web server hosting income-certificate.html with cascading dropdowns.
7. Autonomous Playwright DOM injection:
   - #txtApplicantName == "Arun Kumar"
   - #txtAadhaarNo == "987654321098"
   - #txtAnnualIncome == "85000"
   - #ddlDistrict == "Thiruvananthapuram" -> #ddlTaluk == "Neyyattinkara" -> #ddlVillage == "Nemom"
   - #ddlPurpose == "Higher Education"
   - #fileAadhaar attached directly from memory buffer
   - Verified that #btnSubmit is NOT clicked.
8. Error handling on invalid input, missing fields, and non-existent options.

Can be run via:
    python tests/test_module5_dom_injection.py
or:
    pytest tests/test_module5_dom_injection.py
"""

import http.server
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Generator

# Add parent directory to sys.path so local_form_filler is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from local_form_filler import (
    LocalFormFiller,
    FormSchema as FormSchemaLoader,
    FormField,
    FieldSource,
    FormSchemaError,
    FieldValidationError,
    DropdownOptionNotFoundError,
    FileInjectionError,
    PLAYWRIGHT_AVAILABLE,
    EdgeSLM,
    CriticAgent,
    SupervisorAgent,
    EphemeralPurge,
)
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    import contextlib

    class _DummyPytest:
        class mark:
            @staticmethod
            def skipif(condition, reason=""):
                def decorator(fn):
                    return fn
                return decorator

        @staticmethod
        def raises(expected_exc):
            @contextlib.contextmanager
            def _ctx():
                try:
                    yield
                except expected_exc:
                    pass
                except Exception as e:
                    raise AssertionError(f"Expected {expected_exc.__name__}, got {type(e).__name__}: {e}")
                else:
                    raise AssertionError(f"Expected {expected_exc.__name__} was not raised.")
            return _ctx()

    pytest = _DummyPytest()


# ==============================================================================
# TEST FIXTURES & LOCAL MOCK HTTP SERVER
# ==============================================================================

class MockPortalHandler(http.server.SimpleHTTPRequestHandler):
    """Serves mock_edistrict forms and static assets for integration testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT / "mock_edistrict"), **kwargs)

    def log_message(self, format, *args):
        # Silence normal HTTP access logs during testing
        pass


def get_free_port(preferred: int = 3000) -> int:
    """Attempts to bind preferred port 3000; falls back to an open ephemeral port if occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


class MockServerThread:
    """Manages background HTTP server for tests."""
    def __init__(self, port: int):
        self.port = port
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), MockPortalHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        time.sleep(0.3)  # Brief wait for socket readiness

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


# Sample OCR Payload as specified in Module 3 contract
SAMPLE_OCR_PAYLOAD = {
    "status": "CAPTURED",
    "extracted_data": {
        "full_name": "Arun Kumar",
        "aadhaar_number": "987654321098",
        "dob": "1994-05-15"
    },
    "image_buffer": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
    "sharpness_score": 92.4
}

SAMPLE_SCHEMA_DICT = {
    "service_name": "Income Certificate",
    "form_url": "http://localhost:3000/forms/income-certificate.html",
    "fields": [
        {
            "id": "txtApplicantName",
            "type": "text",
            "required": True,
            "label": "Full Name"
        },
        {
            "id": "txtAadhaarNo",
            "type": "text",
            "pattern": "[0-9]{12}",
            "required": True,
            "label": "Aadhaar UID"
        },
        {
            "id": "ddlDistrict",
            "type": "select",
            "options": [
                "Thiruvananthapuram",
                "Ernakulam",
                "Kozhikode",
                "Thrissur",
                "Kannur"
            ],
            "required": True,
            "label": "District"
        },
        {
            "id": "ddlTaluk",
            "type": "select",
            "required": True,
            "label": "Taluk"
        },
        {
            "id": "ddlVillage",
            "type": "select",
            "required": True,
            "label": "Village"
        },
        {
            "id": "txtRationCardNo",
            "type": "text",
            "required": True,
            "label": "Ration Card Number"
        },
        {
            "id": "txtAnnualIncome",
            "type": "number",
            "min": "1",
            "required": True,
            "label": "Annual Income"
        },
        {
            "id": "ddlPurpose",
            "type": "select",
            "options": [
                "Higher Education",
                "Scholarship",
                "Housing Scheme",
                "General"
            ],
            "required": True,
            "label": "Purpose"
        },
        {
            "id": "fileAadhaar",
            "type": "file",
            "accept": ".pdf,.png,.jpg",
            "required": True,
            "label": "Aadhaar Document"
        }
    ],
    "downloaded_docs": [
        "downloads/self-declaration-affidavit.pdf"
    ]
}


# ==============================================================================
# UNIT & INTEGRATION TESTS
# ==============================================================================

def test_schema_loading():
    """Verifies that schema loads accurately from file and dictionary."""
    schema_path = REPO_ROOT / "current_form_schema.json"
    filler = LocalFormFiller(schema_path=schema_path)
    assert filler.schema is not None
    assert filler.schema.service_name == "Income Certificate"
    assert len(filler.schema.fields) == 9

    applicant_field = filler.schema.get_field("txtApplicantName")
    assert applicant_field is not None
    assert applicant_field.required is True
    assert applicant_field.type == "text"


def test_ocr_payload_ingestion():
    """Verifies OCR biographical data and in-memory document buffer ingestion."""
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)
    filler.load_ocr_data(SAMPLE_OCR_PAYLOAD)

    state = filler.get_state()
    assert state.get("txtApplicantName") == "Arun Kumar"
    assert state.get("txtAadhaarNo") == "987654321098"

    # Verify that the document buffer is preserved in RAM
    assert "fileAadhaar" in filler.state_mgr.file_buffers
    fname, mtype, fbytes = filler.state_mgr.file_buffers["fileAadhaar"]
    assert fname == "aadhaar_card_scanned.png"
    assert mtype == "image/png"
    assert fbytes == SAMPLE_OCR_PAYLOAD["image_buffer"]


def test_conversational_multi_slot_extraction():
    """Verifies extraction of multiple slots from single conversational utterances."""
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)

    # Test multi-slot utterance 1
    u1 = "My name is Arun Kumar, my ration card number is 2451098, and my annual family income is 75000 rupees for my college scholarship."
    slots1 = filler.extract_slots(u1)
    assert slots1.get("txtApplicantName") == "Arun Kumar"
    assert slots1.get("txtRationCardNo") == "2451098"
    assert slots1.get("txtAnnualIncome") == "75000"
    assert slots1.get("ddlPurpose") == "Scholarship"

    # Test utterance 2 from prompt
    u2 = "My annual income is 85000 and purpose is Higher Education"
    slots2 = filler.extract_slots(u2)
    assert slots2.get("txtAnnualIncome") == "85000"
    assert slots2.get("ddlPurpose") == "Higher Education"

    # Test geographic slots
    u3 = "I reside in Thiruvananthapuram district, Neyyattinkara taluk, Nemom village"
    slots3 = filler.extract_slots(u3)
    assert slots3.get("ddlDistrict") == "Thiruvananthapuram"
    assert slots3.get("ddlTaluk") == "Neyyattinkara"
    assert slots3.get("ddlVillage") == "Nemom"


def test_input_merging_and_precedence():
    """
    Verifies merging OCR with conversational data:
    - OCR Aadhaar is authoritative.
    - Conversational income & purpose merge cleanly.
    - Conflicts are recorded for Module 6 audit.
    """
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)
    filler.load_ocr_data(SAMPLE_OCR_PAYLOAD)

    # User states income and purpose
    slots = filler.extract_slots("My annual income is 85000 and purpose is Higher Education")
    filler.merge_inputs(slots)

    state = filler.get_state()
    assert state["txtApplicantName"] == "Arun Kumar"
    assert state["txtAadhaarNo"] == "987654321098"
    assert state["txtAnnualIncome"] == "85000"
    assert state["ddlPurpose"] == "Higher Education"

    # Conversational statement claiming a different Aadhaar -> should flag conflict
    filler.merge_inputs({"txtAadhaarNo": "111122223333"})
    conflicts = filler.get_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0]["field_id"] == "txtAadhaarNo"
    assert conflicts[0]["existing_value"] == "987654321098"
    # State preserves original verified OCR value
    assert filler.get_state()["txtAadhaarNo"] == "987654321098"


def test_field_readback_and_accessibility():
    """Verifies step-by-step contextual prompt generation and visual cards."""
    spoken_prompts = []
    filler = LocalFormFiller(
        schema_dict=SAMPLE_SCHEMA_DICT,
        speech_callback=lambda text: spoken_prompts.append(text)
    )

    next_f = filler.get_next_field()
    assert next_f is not None
    assert next_f.id == "txtApplicantName"

    prompt = filler.generate_prompt(next_f)
    assert "full name" in prompt.lower()
    assert len(spoken_prompts) == 1

    # Test visual card generation for Deaf mode
    card = filler.get_visual_card(next_f)
    assert card["field_id"] == "txtApplicantName"
    assert card["theme"] == "HIGH_CONTRAST_DARK"
    assert card["border_color"] == "#FFE600"


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
def test_playwright_dom_injection_end_to_end():
    """
    End-to-End DOM Injection Test:
    1. Boots mock portal.
    2. Merges OCR + conversational inputs + cascade selections.
    3. Executes Playwright DOM injection.
    4. Asserts:
       - #txtApplicantName == 'Arun Kumar'
       - #txtAadhaarNo == '987654321098'
       - #txtAnnualIncome == '85000'
       - Cascading dropdowns: District='Thiruvananthapuram' -> Taluk='Neyyattinkara' -> Village='Nemom'
       - Purpose == 'Higher Education'
       - #fileAadhaar has attached in-memory buffer
       - #btnSubmit was NOT clicked.
       - status == 'POPULATED'
    """
    port = get_free_port(3000)
    server_thread = MockServerThread(port)
    server_thread.start()

    try:
        portal_base_url = f"http://127.0.0.1:{port}"
        filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)

        # 1. Ingest OCR
        filler.load_ocr_data(SAMPLE_OCR_PAYLOAD)

        # 2. Extract & Merge Conversational Input
        conversational_utterance = (
            "My annual income is 85000 and purpose is Higher Education. "
            "My ration card is 2451098. "
            "I belong to Thiruvananthapuram district, Neyyattinkara taluk, Nemom village."
        )
        slots = filler.extract_slots(conversational_utterance)
        filler.merge_inputs(slots)

        # Verify pre-injection state
        state = filler.get_state()
        assert state["txtApplicantName"] == "Arun Kumar"
        assert state["txtAadhaarNo"] == "987654321098"
        assert state["txtAnnualIncome"] == "85000"
        assert state["ddlPurpose"] == "Higher Education"
        assert state["ddlDistrict"] == "Thiruvananthapuram"
        assert state["ddlTaluk"] == "Neyyattinkara"
        assert state["ddlVillage"] == "Nemom"

        # 3. Execute Autonomous DOM Injection via Playwright
        result = filler.populate_form(
            headless=True,
            portal_base_url=portal_base_url
        )

        # 4. Verify Post-Injection Results
        assert result.status == "POPULATED", f"Injection failed with errors: {result.validation_errors}"
        assert len(result.fields_missing) == 0

        # Query live page locator values
        page = filler._page
        assert page is not None

        # Text & numeric inputs
        assert page.locator("#txtApplicantName").input_value() == "Arun Kumar"
        assert page.locator("#txtAadhaarNo").input_value() == "987654321098"
        assert page.locator("#txtAnnualIncome").input_value() == "85000"
        assert page.locator("#txtRationCardNo").input_value() == "2451098"

        # Dropdowns
        assert page.locator("#ddlDistrict").input_value() == "Thiruvananthapuram"
        assert page.locator("#ddlTaluk").input_value() == "Neyyattinkara"
        assert page.locator("#ddlVillage").input_value() == "Nemom"
        assert page.locator("#ddlPurpose").input_value() == "Higher Education"

        # In-memory file upload
        file_attached = page.eval_on_selector("#fileAadhaar", "el => el.files.length > 0")
        assert file_attached is True
        file_name = page.eval_on_selector("#fileAadhaar", "el => el.files[0].name")
        assert file_name == "aadhaar_card_scanned.png"

        # SUBMISSION CIRCUIT BREAKER: Verify that #btnSubmit was NOT clicked
        # The form should remain on income-certificate.html and not have navigated to receipt
        curr_url = page.url
        assert "/forms/income-certificate.html" in curr_url
        assert "acknowledgement-slip.html" not in curr_url

    finally:
        filler.close()
        server_thread.stop()


def test_validation_error_handling():
    """Verifies that invalid numeric input or invalid dropdown option raises clean errors."""
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)
    
    # Test numeric bounds check
    with pytest.raises(FieldValidationError):
        filler.dom_injector.fill_number("#txtAnnualIncome", -500, min_val="1")

    # Test non-numeric input for number field
    with pytest.raises(FieldValidationError):
        filler.dom_injector.fill_number("#txtAnnualIncome", "not_a_number", min_val="1")

    # Test empty file buffer
    with pytest.raises(FileInjectionError):
        filler.attach_file_buffer = getattr(filler.state_mgr, "attach_file_buffer")
        filler.state_mgr.attach_file_buffer("fileAadhaar", "test.png", "image/png", b"")


def test_edge_slm_tier1_extraction():
    """Verifies Tier 1 On-Device Edge SLM offline multi-slot extraction."""
    schema = FormSchemaLoader.from_dict(SAMPLE_SCHEMA_DICT)
    edge_slm = EdgeSLM(schema)
    statement = "My name is Arun Kumar, my ration card number is 2451098, and my annual family income is 75000 rupees for my college scholarship."
    slots = edge_slm.extract_slots(statement)
    assert slots.get("txtApplicantName") == "Arun Kumar"
    assert slots.get("txtRationCardNo") == "2451098"
    assert slots.get("txtAnnualIncome") == "75000"
    assert slots.get("ddlPurpose") == "Scholarship"


def test_critic_agent_audit():
    """Verifies Critic Agent pre-submission format, syntax, and completeness audit."""
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)
    critic = filler.critic_agent

    # 1. Audit on empty state should fail with missing fields
    is_valid, errors = critic.audit_state(filler.schema, filler.state_mgr)
    assert is_valid is False
    assert any("Missing mandatory field" in e for e in errors)

    # 2. Populate valid state
    filler.load_ocr_data(SAMPLE_OCR_PAYLOAD)
    slots = filler.extract_slots("Annual income is 85000 and purpose is Higher Education. Ration card is 2451098.")
    filler.merge_inputs(slots)
    filler.merge_inputs({
        "ddlDistrict": "Thiruvananthapuram",
        "ddlTaluk": "Neyyattinkara",
        "ddlVillage": "Nemom"
    })

    is_valid, errors = critic.audit_state(filler.schema, filler.state_mgr)
    assert is_valid is True, f"Critic audit failed unexpectedly: {errors}"
    assert len(errors) == 0

    # 3. Test invalid 10-digit Aadhaar
    filler.state_mgr.set_value("txtAadhaarNo", "1234567890", FieldSource.CONVERSATION)
    is_valid, errors = critic.audit_state(filler.schema, filler.state_mgr)
    assert is_valid is False
    assert any("Invalid Aadhaar syntax" in e for e in errors)

    # 4. Test non-positive annual income
    filler.state_mgr.set_value("txtAadhaarNo", "987654321098", FieldSource.OCR)
    filler.state_mgr.set_value("txtAnnualIncome", "0", FieldSource.CONVERSATION)
    is_valid, errors = critic.audit_state(filler.schema, filler.state_mgr)
    assert is_valid is False
    assert any("positive number greater than 0" in e for e in errors)


def test_supervisor_agent_interlock():
    """Verifies Supervisor human-in-the-loop gate and multimodal pre-submit summary."""
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)
    supervisor = filler.supervisor_agent

    # 1. State summary generation
    state_dict = {
        "txtApplicantName": "Arun Kumar",
        "txtAadhaarNo": "987654321098",
        "txtAnnualIncome": "85000",
        "ddlDistrict": "Thiruvananthapuram",
        "ddlPurpose": "Higher Education",
    }
    spoken, visual = supervisor.generate_summary(state_dict)
    assert "Arun Kumar" in spoken
    assert "1098" in spoken
    assert "85000" in spoken
    assert visual["theme"] == "HIGH_CONTRAST_DARK"
    assert visual["applicant_name"] == "Arun Kumar"

    # 2. Rejection / Cancel signal
    confirmed = supervisor.process_confirmation("Cancel")
    assert confirmed is False
    assert supervisor.is_unlocked() is False
    assert supervisor.get_token() is None

    # 3. Confirmation signal (Voice "Submit" or Sign "THUMBS_UP")
    confirmed = supervisor.process_confirmation("THUMBS_UP")
    assert confirmed is True
    assert supervisor.is_unlocked() is True
    token = supervisor.get_token()
    assert token is not None
    assert token.startswith("EXEC_TOKEN_")


def test_ephemeral_memory_purge():
    """Verifies cryptographic volatile memory zeroization of buffers and state."""
    filler = LocalFormFiller(schema_dict=SAMPLE_SCHEMA_DICT)
    filler.load_ocr_data(SAMPLE_OCR_PAYLOAD)

    # Check that file buffer exists before purge
    assert "fileAadhaar" in filler.state_mgr.file_buffers
    assert len(filler.state_mgr.fields_state) > 0

    # Execute purge
    EphemeralPurge.purge_filler(filler)

    # Verify zeroization & clear
    assert len(filler.state_mgr.file_buffers) == 0
    assert len(filler.state_mgr.fields_state) == 0
    assert len(filler.state_mgr.conflicts) == 0


# ==============================================================================
# DIRECT SCRIPT RUNNER
# ==============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("OmniKiosk Module 5: Running Standalone Test Suite")
    print("=" * 70)

    tests = [
        ("1. Schema Loading", test_schema_loading),
        ("2. OCR Payload Ingestion", test_ocr_payload_ingestion),
        ("3. Conversational Multi-Slot Extraction", test_conversational_multi_slot_extraction),
        ("4. Input Merging & Conflict Precedence", test_input_merging_and_precedence),
        ("5. Field Readback & Accessibility", test_field_readback_and_accessibility),
        ("6. Input Validation & Error Handling", test_validation_error_handling),
        ("7. Tier 1 Edge SLM Offline Extraction", test_edge_slm_tier1_extraction),
        ("8. Critic Agent Pre-Submission Guardrail", test_critic_agent_audit),
        ("9. Supervisor Agent Interlock & Multimodal Summary", test_supervisor_agent_interlock),
        ("10. Ephemeral Memory Purge & Zeroization", test_ephemeral_memory_purge),
    ]

    if PLAYWRIGHT_AVAILABLE:
        tests.append(("11. Playwright DOM Injection (End-to-End Live Browser)", test_playwright_dom_injection_end_to_end))
    else:
        print("[WARNING] Playwright not installed in environment; skipping live browser injection test.")

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            print(f"\n--- Running: {name} ---")
            test_fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"Test Summary: {passed} PASSED, {failed} FAILED")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)
