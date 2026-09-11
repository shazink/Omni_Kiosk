# Module 2: Cloud Navigator, Document Discovery & Doubt-Clearing

Autonomous discovery layer for OmniKiosk public civic services with zero citizen PII exposure.

---

## Directory Structure

```
module_2/
├── __init__.py                     # Package exports
├── cloud_navigator.py              # Primary Module 2 execution engine
├── request_router.py               # Dual-tier PII request dispatcher
├── test_groq_api.py                # Standalone Groq API live diagnostic runner
├── test_module2_cloud_nav.py       # Comprehensive 7-part automated test suite
├── current_form_schema.json        # Serialized form schema artifact
├── .env                            # Active API keys and environment settings
├── .env.example                    # Template environment file
└── README.md                       # Module documentation
```

---

## Quick Start

### 1. Interactive CLI Mode
Run Module 2 interactively:
```bash
python module_2/cloud_navigator.py
```
Or with an initial natural-language intent:
```bash
python module_2/cloud_navigator.py --intent "I need an income certificate for college"
```

### 2. Verify Live Groq LLM
Test your Groq API key and 2-sentence doubt-clearing response:
```bash
python -m module_2.test_groq_api
```

### 3. Run Automated Tests
Run the complete unit & integration test suite:
```bash
python module_2/test_module2_cloud_nav.py
```
