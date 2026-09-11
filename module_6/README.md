# OmniKiosk: Autonomous Civic Service Terminal
## Module 6: Multi-Agent Governance, Supervisor Verification & Ephemeral Privacy Purge

OmniKiosk is an autonomous, accessibility-first civic service terminal engineered for public administration (government, healthcare, civic portals). It enables blind, low-vision, deaf, non-verbal, motor-impaired, and **deafblind** citizens to discover, fill, and submit official applications without manual barriers and with zero risk of cloud PII exposure.

---

## 🌟 New Feature: First-Class DEAFBLIND MODE
> **Design Principle:** *"No sight. No sound. Still independent."*

OmniKiosk provides a dedicated hardware abstraction layer for citizens who are **both blind and deaf**, communicating entirely via:
1. **Configurable Tactile Haptic Pulses** (Information, Warnings, Errors, Success, Cancellation).
2. **Refreshable Braille Pin Matrix Display** (Grade 1 Unicode Braille cells with sensitive UID masking).
3. **Physical Tactile Input Controls** (`Button A` = Confirm / Submit, `Button B` = Cancel / Abort).

---

## 🏗️ Multi-Agent Governance Architecture (Module 6)

```
                            [ POPULATED FORM STATE ]
                                       │
                                       ▼
                        [ CRITIC AGENT (Pre-Submission) ]
                        • Aadhaar 12-digit & Verhoeff checksum
                        • Positive income validation (> 0)
                        • Mandatory selects & file checks
                        • Voice vs OCR Name discrepancy check (Levenshtein)
                                       │
                                       ├── [FAIL] ──► Block Submit & Emit Tactile/Visual ERROR
                                       │
                                       ▼ [PASS]
                       [ SUPERVISOR AGENT (Circuit Breaker) ]
                        • Generates 1-time single-use SubmissionToken
                        • Formats PII-masked Structured Summary
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   [ BLIND MODE ]                [ DEAF MODE ]               [ DEAFBLIND MODE ]
   • Directional TTS             • High-Contrast Card        • Tactile Pulse Pattern
   • Spoken "Submit"             • Thumbs-Up Gesture         • Physical Buttons [A/B]
                                                             • Masked Braille Pins
         └─────────────────────────────┬─────────────────────────────┘
                                       │
                                       ▼
                          [ CITIZEN CONFIRMATION GATE ]
                                       │
                           ┌───────────┴───────────┐
                           ▼                       ▼
                      [ CONFIRM ]              [ CANCEL / TIMEOUT ]
                           │                       │
                           ▼                       ▼
                [ TOKEN CONSUMPTION & POST ]   [ CANCEL & PURGE ]
                • 1-time token consumed
                • Submit form to portal API
                           │
                           ▼
                [ RECEIPT VERIFICATION ]
                • Scrapes & verifies KL-EDIST-2026-XXXX
                • Delivers receipt via active mode adapter
                           │
                           ▼
                [ ZERO-TRACE EPHEMERAL PURGE ]
                • RAM buffer zeroization (sodium_memzero)
                • Form PII cleared, tokens invalidated
                • Departure watchdog triggers emergency purge
```

---

## 📋 Tactile Vibration Patterns

| Event Type | Pattern Name | Symbol | Pulse Timing (ms) | Description |
|---|---|---|---|---|
| `INFO` | `SHORT_PULSE` | `●` | `[200]` | One short vibration pulse (Information/Notice) |
| `WARNING` | `DOUBLE_PULSE` | `● ●` | `[200, 100, 200]` | Two short vibration pulses (Warning/Attention) |
| `ERROR` | `LONG_PULSE` | `▬▬▬` | `[800]` | One long vibration pulse (Error/Audit failed) |
| `SUCCESS` | `TRIPLE_PULSE` | `● ● ●` | `[150, 100, 150, 100, 150]` | Three short rapid pulses (Success/Receipt issued) |
| `CANCEL` | `LONG_SHORT_PULSE` | `▬▬ ●` | `[600, 150, 150]` | Long pulse followed by short pulse (Aborted) |

---

## 🧪 Comprehensive Verification Suite

Run all isolated module tests and the unified end-to-end integration demo:

```bash
# 1. Module 6 Core Tests (Critic, Supervisor, Deafblind, Token, Purge):
python3 tests/test_module6_governance_purge.py

# 2. Module 1 Civic Portal Tests:
python3 tests/test_module1_portal.py

# 3. Module 2 Cloud Navigator Tests:
python3 tests/test_module2_cloud_nav.py

# 4. Module 3 Vision Scanner & OCR Tests:
python3 tests/test_module3_vision_ocr.py

# 5. Module 4 Accessibility & Gesture Tests:
python3 tests/test_module4_accessibility.py

# 6. Module 5 Form Filler Tests:
python3 tests/test_module5_dom_injection.py

# 7. Complete Integrated Multi-Agent Demo:
python3 run_omnikiosk_demo.py
```
