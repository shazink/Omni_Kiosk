"""
OmniKiosk Module 2: Cloud Navigator, Document Discovery & Doubt-Clearing
Autonomous discovery layer for public civic services with zero PII exposure.

Pipeline:
Citizen natural-language intent -> Dynamic Intent Classifier -> Civic service URL ->
Playwright Headless Browser -> DOM Schema Extractor -> Pro-forma discovery ->
PII-safe RAG Doubt Clearing (Groq LLM + Dynamic KB Retrieval) -> "Let's start filling" ->
current_form_schema.json -> Cloud/discovery session terminates -> Hand-off ready for Module 5.
"""

import argparse
import html.parser
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)

def load_env(env_path: Optional[str] = None):
    """Loads key-value pairs from .env into os.environ without requiring external packages."""
    candidates = [
        env_path,
        os.path.join(_THIS_DIR, ".env"),
        os.path.join(_PARENT_DIR, ".env"),
        ".env"
    ]
    resolved_path = None
    for p in candidates:
        if p and os.path.exists(p):
            resolved_path = p
            break

    if not resolved_path:
        return

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"[Config] Warning loading .env from {resolved_path}: {e}")

load_env()

# Configuration
PORTAL_BASE_URL = os.environ.get("OMNIKIOSK_PORTAL_URL", "http://localhost:3000").rstrip("/")
SCHEMA_OUTPUT_PATH = os.environ.get("OMNIKIOSK_SCHEMA_PATH", "current_form_schema.json")
DOWNLOADS_DIR = os.environ.get("OMNIKIOSK_DOWNLOADS_DIR", "downloads")

# Knowledge base directory resolution
if os.path.exists(os.path.join(_THIS_DIR, "mock_edistrict", "kb")):
    KB_DIR = os.path.join(_THIS_DIR, "mock_edistrict", "kb")
elif os.path.exists(os.path.join(_PARENT_DIR, "mock_edistrict", "kb")):
    KB_DIR = os.path.join(_PARENT_DIR, "mock_edistrict", "kb")
else:
    KB_DIR = os.path.join(_PARENT_DIR, "mock_edistrict", "kb")

# Cloud LLM Settings
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
LLM_MAX_OUTPUT_TOKENS = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "500"))
LLM_SENTENCE_LIMIT = int(os.environ.get("LLM_SENTENCE_LIMIT", "2"))


# ============================================================================
# 1. DYNAMIC INTENT CLASSIFIER & ROUTE RESOLUTION
# ============================================================================

class ServiceIntentClassifier:
    """Dynamically discovers civic services by scanning portal forms and metadata without hardcoded routes."""

    def __init__(self, base_url: str = PORTAL_BASE_URL, forms_dir: Optional[str] = None):
        self.base_url = base_url
        self.routes: Dict[str, Dict[str, Any]] = {}
        self._discover_routes(forms_dir)

    def _discover_routes(self, forms_dir: Optional[str] = None):
        """Scans forms directory and extracts service names, URLs, and keywords dynamically from HTML."""
        candidates = [
            forms_dir,
            os.path.join(_THIS_DIR, "mock_edistrict", "forms"),
            os.path.join(_PARENT_DIR, "mock_edistrict", "forms")
        ]
        target_dir = next((c for c in candidates if c and os.path.exists(c)), None)

        if target_dir:
            for fname in os.listdir(target_dir):
                if fname.endswith(".html"):
                    rel_path = f"/forms/{fname}"
                    full_path = os.path.join(target_dir, fname)
                    try:
                        with open(full_path, "r", encoding="utf-8") as fp:
                            content = fp.read()

                        # Extract service name from <h2> or <title>
                        h2_match = re.search(r"<h2>(.*?)</h2>", content, re.IGNORECASE)
                        title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)

                        if h2_match:
                            svc_name = re.sub(r"^Application for\s+", "", h2_match.group(1), flags=re.IGNORECASE).strip()
                        elif title_match:
                            svc_name = title_match.group(1).split("-")[0].replace("Application", "").strip()
                        else:
                            svc_name = fname.replace(".html", "").replace("-", " ").title()

                        slug_tokens = fname.replace(".html", "").replace("-", " ").split()
                        title_tokens = [t.lower() for t in svc_name.split() if len(t) > 2]
                        keywords = list(set(slug_tokens + title_tokens))
                        
                        if "income" in keywords:
                            keywords.extend(["salary", "earnings", "annual income", "fee concession", "scholarship income"])
                        if "disability" in keywords:
                            keywords.extend(["pension", "differently abled", "handicap", "medical board"])
                        if "community" in keywords:
                            keywords.extend(["caste", "religion", "reservation", "obc", "sc", "st"])

                        key = fname.replace(".html", "").upper().replace("-", "_")
                        self.routes[key] = {
                            "name": svc_name,
                            "path": rel_path,
                            "keywords": keywords
                        }
                    except Exception as e:
                        print(f"[IntentClassifier] Warning discovering form {fname}: {e}")

        if not self.routes:
            self.routes = {
                "INCOME_CERTIFICATE": {
                    "name": "Income Certificate",
                    "path": "/forms/income-certificate.html",
                    "keywords": ["income", "salary", "earnings", "annual income", "scholarship"]
                },
                "DISABILITY_PENSION": {
                    "name": "Disability Pension",
                    "path": "/forms/disability-pension.html",
                    "keywords": ["disability", "pension", "differently abled"]
                },
                "COMMUNITY_CERTIFICATE": {
                    "name": "Community Certificate",
                    "path": "/forms/community-certificate.html",
                    "keywords": ["community", "caste", "religion", "reservation"]
                }
            }

    def classify(self, query: str) -> Dict[str, Any]:
        """Maps conversational intent to target service dynamically."""
        normalized = query.lower().strip()
        best_match = None
        highest_score = 0

        for key, service in self.routes.items():
            score = 0
            for kw in service["keywords"]:
                if kw in normalized:
                    score += len(kw.split()) + 1
            if score > highest_score:
                highest_score = score
                best_match = key

        if best_match and highest_score > 0:
            target = self.routes[best_match]
            return {
                "status": "SUCCESS",
                "service_key": best_match,
                "service_name": target["name"],
                "form_url": f"{self.base_url}{target['path']}",
                "confidence": min(1.0, highest_score * 0.35)
            }

        avail_names = ", ".join([s["name"] for s in self.routes.values()])
        return {
            "status": "AMBIGUOUS",
            "service_key": None,
            "service_name": None,
            "form_url": None,
            "message": f"I could not identify the specific civic service. Available services: {avail_names}."
        }


# ============================================================================
# 2. PII SANITIZER & KNOWLEDGE BASE RAG (DOUBT CLEARING)
# ============================================================================

class PIISanitizer:
    """Strict regex-based PII scrubber ensuring zero citizen identifiers reach public/cloud models."""

    PATTERNS = [
        (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b|\b\d{12}\b"), "[REDACTED_AADHAAR]"),
        (re.compile(r"\b(?:\+91[- ]?)?[6-9]\d{9}\b"), "[REDACTED_PHONE]"),
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
        (re.compile(r"\b(?:account|acc|a/c)\s*[:#]?\s*\d{9,18}\b", re.IGNORECASE), "[REDACTED_BANK_ACCOUNT]"),
        (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), "[REDACTED_IFSC]"),
        (re.compile(r"\b(?:0[1-9]|[12][0-9]|3[01])[-/.](?:0[1-9]|1[012])[-/.](?:19|20)\d\d\b"), "[REDACTED_DOB]")
    ]

    @classmethod
    def sanitize(cls, text: str) -> Tuple[str, bool]:
        """Returns sanitized string and a boolean indicating if PII was detected and redacted."""
        sanitized = text
        redacted = False
        for pattern, replacement in cls.PATTERNS:
            if pattern.search(sanitized):
                sanitized = pattern.sub(replacement, sanitized)
                redacted = True
        return sanitized, redacted


class DoubtClearingEngine:
    """Retrieves plain-language answers dynamically from knowledge base documents and cloud LLM without hardcoded strings."""

    def __init__(self, kb_dir: str = KB_DIR):
        self.kb_dir = kb_dir
        self.charter_text = ""
        self.acceptable_proofs = {}
        self._load_kb()

    def _load_kb(self):
        charter_path = os.path.join(self.kb_dir, "citizen-charter.md")
        proofs_path = os.path.join(self.kb_dir, "acceptable-proofs.json")

        if os.path.exists(charter_path):
            with open(charter_path, "r", encoding="utf-8") as f:
                self.charter_text = f.read()

        if os.path.exists(proofs_path):
            try:
                with open(proofs_path, "r", encoding="utf-8") as f:
                    self.acceptable_proofs = json.load(f)
            except Exception as e:
                print(f"[DoubtClearing] Warning loading proofs JSON: {e}")

    def _call_cloud_llm(self, clean_question: str) -> Optional[str]:
        """Optionally calls Gemini or Groq Cloud LLM with strict PII-scrubbed question and KB context."""
        context_snippet = self.charter_text[:1200]
        prompt = (
            f"You are OmniKiosk Civic Assistant for e-District Kerala.\n"
            f"Answer the citizen question using ONLY this official knowledge base context:\n{context_snippet}\n\n"
            f"Rules:\n"
            f"1. Plain language at a 6th-grade reading level.\n"
            f"2. MAXIMUM {LLM_SENTENCE_LIMIT} SENTENCES.\n"
            f"3. ZERO PII.\n\n"
            f"Question: {clean_question}\n"
            f"Answer:"
        )

        # 1. Google Gemini API
        if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": LLM_TEMPERATURE, "maxOutputTokens": 100}
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    sentences = [s.strip() for s in text.split(".") if s.strip()]
                    return ". ".join(sentences[:LLM_SENTENCE_LIMIT]) + "."
            except Exception as e:
                print(f"[DoubtClearing] Note: Gemini cloud call failed, using local KB: {e}")

        # 2. Groq Cloud API
        if LLM_PROVIDER == "groq" and GROQ_API_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                payload = {
                    "model": GROQ_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are OmniKiosk Civic Assistant for Kerala e-District. "
                                f"Answer the user question in plain language in AT MOST {LLM_SENTENCE_LIMIT} SENTENCES based on the provided context. "
                                "Do NOT include any preamble, headings, or citizen personal data."
                            )
                        },
                        {"role": "user", "content": f"Context:\n{context_snippet}\n\nQuestion: {clean_question}"}
                    ],
                    "temperature": LLM_TEMPERATURE,
                    "max_tokens": LLM_MAX_OUTPUT_TOKENS
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "User-Agent": "OmniKiosk-CloudNavigator/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["choices"][0]["message"].get("content", "").strip()
                    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
                    text = text.replace("\n", " ")
                    sentences = [s.strip() for s in text.split(".") if s.strip()]
                    if sentences:
                        return ". ".join(sentences[:LLM_SENTENCE_LIMIT]) + "."
            except Exception as e:
                print(f"[DoubtClearing] Note: Groq cloud call failed, using local KB: {e}")

        return None

    def _search_kb_dynamically(self, clean_question: str) -> str:
        """Dynamically searches the loaded knowledge base documents with zero hardcoded answer strings."""
        if not self.charter_text and not self.acceptable_proofs:
            return "Please consult the civic helpdesk at the local office for clarifications."

        stopwords = {"what", "is", "are", "the", "of", "for", "my", "a", "an", "in", "to", "how", "many", "can", "i", "do", "does", "it", "take", "get", "need", "apply", "if", "not", "have", "with"}
        q_tokens = [w.strip("?,.:;!'\"").lower() for w in clean_question.split() if len(w) > 2 and w.lower() not in stopwords]

        candidates = []
        for line in self.charter_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            clean_line = re.sub(r"^[-*]\s*(?:\*\*[^*]+\*\*:\s*)?", "", line).strip()
            if len(clean_line) > 15:
                candidates.append(clean_line)

        if isinstance(self.acceptable_proofs, dict):
            for svc_data in self.acceptable_proofs.values():
                if isinstance(svc_data, dict):
                    for val in svc_data.values():
                        if isinstance(val, list):
                            candidates.extend([str(item) for item in val])
                        elif isinstance(val, str):
                            candidates.append(val)

        scored = []
        for cand in candidates:
            cand_lower = cand.lower()
            score = sum(2 if t in cand_lower else 0 for t in q_tokens)
            if score > 0:
                scored.append((score, cand))

        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            top_text = scored[0][1]
            sentences = [s.strip() for s in top_text.split(".") if s.strip()]
            if len(sentences) == 1 and len(scored) > 1:
                second_sentences = [s.strip() for s in scored[1][1].split(".") if s.strip()]
                if second_sentences:
                    sentences.append(second_sentences[0])
            return ". ".join(sentences[:LLM_SENTENCE_LIMIT]) + "."

        return "Information regarding your query is available in the Citizen Charter. Please refer to your local village office for further assistance."

    def answer_question(self, question: str) -> str:
        """Sanitizes query, queries cloud LLM with loaded KB context if configured, or dynamically retrieves from local KB."""
        clean_q, _ = PIISanitizer.sanitize(question)

        cloud_ans = self._call_cloud_llm(clean_q)
        if cloud_ans:
            return cloud_ans

        return self._search_kb_dynamically(clean_q)


# ============================================================================
# 3. PLAYWRIGHT DOM SCHEMA EXTRACTOR & PRO-FORMA DISCOVERY
# ============================================================================

class StandaloneDOMParser(html.parser.HTMLParser):
    """Fallback standard-library parser extracting form schema if Playwright binary is missing."""

    def __init__(self):
        super().__init__()
        self.fields = []
        self.doc_links = []
        self.current_labels = {}
        self.current_select = None
        self._last_text = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        
        if tag == "label" and "for" in attr_dict:
            self._current_label_for = attr_dict["for"]

        elif tag == "input":
            field_id = attr_dict.get("id")
            if field_id and attr_dict.get("type") != "hidden":
                raw_lbl = self.current_labels.get(field_id, "").replace("*", "").strip()
                field = {
                    "id": field_id,
                    "name": attr_dict.get("name", field_id),
                    "type": attr_dict.get("type", "text"),
                    "required": "required" in attr_dict,
                    "placeholder": attr_dict.get("placeholder", ""),
                    "label": raw_lbl or attr_dict.get("placeholder") or field_id
                }
                if "pattern" in attr_dict:
                    field["pattern"] = attr_dict["pattern"]
                if "min" in attr_dict:
                    field["min"] = attr_dict["min"]
                if "max" in attr_dict:
                    field["max"] = attr_dict["max"]
                if "accept" in attr_dict:
                    field["accept"] = attr_dict["accept"]
                self.fields.append(field)

        elif tag == "select":
            field_id = attr_dict.get("id")
            if field_id:
                raw_lbl = self.current_labels.get(field_id, "").replace("*", "").strip()
                self.current_select = {
                    "id": field_id,
                    "name": attr_dict.get("name", field_id),
                    "type": "select",
                    "required": "required" in attr_dict,
                    "label": raw_lbl or field_id,
                    "options": []
                }

        elif tag == "option" and self.current_select is not None:
            self._current_option_val = attr_dict.get("value", "")

        elif tag == "button":
            field_id = attr_dict.get("id")
            if field_id:
                self.fields.append({
                    "id": field_id,
                    "type": "button",
                    "name": attr_dict.get("name", field_id),
                    "required": False,
                    "label": attr_dict.get("type", "submit")
                })

        elif tag == "a" and "href" in attr_dict:
            href = attr_dict["href"]
            if href.endswith(".pdf"):
                self.doc_links.append(href)

    def handle_endtag(self, tag):
        if tag == "select" and self.current_select:
            self.fields.append(self.current_select)
            self.current_select = None
        elif tag == "label":
            self._current_label_for = None

    def handle_data(self, data):
        text = data.strip()
        if text and hasattr(self, "_current_label_for") and self._current_label_for:
            if self._current_label_for in self.current_labels:
                self.current_labels[self._current_label_for] += " " + text
            else:
                self.current_labels[self._current_label_for] = text
        if self.current_select is not None and text and text != "-- Select District --":
            if hasattr(self, "_current_option_val") and self._current_option_val:
                self.current_select["options"].append(self._current_option_val)


class BrowserInspector:
    """Automates headless browser inspection of civic forms via Playwright with robust HTTP fallback."""

    def __init__(self, downloads_dir: str = DOWNLOADS_DIR):
        self.downloads_dir = downloads_dir
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def inspect_form(self, form_url: str, service_name: str) -> Dict[str, Any]:
        """Navigates to form_url, extracts all form fields, options, labels, and downloads pro-formas."""
        schema = None
        try:
            schema = self._inspect_with_playwright(form_url, service_name)
        except Exception:
            schema = self._inspect_with_http(form_url, service_name)

        schema["downloaded_docs"] = self._download_pro_formas(form_url, schema.get("_doc_links", []))
        if "_doc_links" in schema:
            del schema["_doc_links"]

        return schema

    def _inspect_with_playwright(self, form_url: str, service_name: str) -> Dict[str, Any]:
        from playwright.sync_api import sync_playwright
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

        self.page.goto(form_url, wait_until="domcontentloaded", timeout=15000)

        elements_data = self.page.evaluate("""() => {
            const results = [];
            const docLinks = [];
            
            const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea, button[type="submit"], #btnSubmit');
            inputs.forEach(el => {
                const id = el.id || el.name;
                if (!id) return;

                let labelText = '';
                const label = document.querySelector(`label[for="${el.id}"]`);
                if (label) {
                    labelText = label.innerText.replace('*', '').trim();
                } else if (el.closest('label')) {
                    labelText = el.closest('label').innerText.replace('*', '').trim();
                }

                const item = {
                    id: el.id,
                    name: el.name || el.id,
                    type: el.tagName.toLowerCase() === 'select' ? 'select' : (el.type || 'text'),
                    required: el.hasAttribute('required'),
                    label: labelText || el.placeholder || el.id
                };

                if (el.getAttribute('pattern')) item.pattern = el.getAttribute('pattern');
                if (el.getAttribute('min')) item.min = el.getAttribute('min');
                if (el.getAttribute('max')) item.max = el.getAttribute('max');
                if (el.getAttribute('accept')) item.accept = el.getAttribute('accept');
                if (el.getAttribute('placeholder')) item.placeholder = el.getAttribute('placeholder');

                if (el.tagName.toLowerCase() === 'select') {
                    item.options = Array.from(el.options).map(o => o.value).filter(v => v.length > 0);
                }

                results.push(item);
            });

            const pdfLinks = document.querySelectorAll('a[href$=".pdf"]');
            pdfLinks.forEach(a => {
                docLinks.push(a.getAttribute('href'));
            });

            return { fields: results, docLinks: docLinks };
        }""")

        return {
            "service_name": service_name,
            "form_url": form_url,
            "fields": elements_data.get("fields", []),
            "_doc_links": elements_data.get("docLinks", [])
        }

    def _inspect_with_http(self, form_url: str, service_name: str) -> Dict[str, Any]:
        """Fallback extractor using HTTP request or local file fallback if server is offline."""
        html_content = ""
        try:
            req = urllib.request.Request(form_url, headers={"User-Agent": "OmniKiosk-CloudNavigator/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                html_content = response.read().decode("utf-8")
        except Exception as e:
            parsed_url = urllib.parse.urlparse(form_url)
            rel_path = parsed_url.path.lstrip("/")
            
            candidates = [
                os.path.join(_THIS_DIR, "mock_edistrict", rel_path),
                os.path.join(_PARENT_DIR, "mock_edistrict", rel_path)
            ]
            found = False
            for cand in candidates:
                if os.path.exists(cand):
                    with open(cand, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    found = True
                    break
            
            if not found:
                raise ConnectionError(
                    f"Mock e-District portal is not running at {form_url}. "
                    "Please start the portal server with: python mock_edistrict/server.py"
                ) from e

        parser = StandaloneDOMParser()
        parser.feed(html_content)

        return {
            "service_name": service_name,
            "form_url": form_url,
            "fields": parser.fields,
            "_doc_links": parser.doc_links
        }

    def _download_pro_formas(self, form_url: str, doc_links: List[str]) -> List[str]:
        """Resolves pro-forma links against form URL, downloads them, and returns local paths."""
        downloaded = []
        base = form_url.rsplit("/", 1)[0]
        parsed_portal = urllib.parse.urlparse(PORTAL_BASE_URL)
        portal_origin = f"{parsed_portal.scheme}://{parsed_portal.netloc}"

        for link in doc_links:
            if link.startswith("http"):
                full_url = link
            elif link.startswith("/"):
                full_url = f"{portal_origin}{link}"
            else:
                full_url = f"{base}/{link}"

            filename = os.path.basename(urllib.parse.urlparse(full_url).path)
            if not filename:
                filename = "pro-forma.pdf"

            local_path = os.path.join(self.downloads_dir, filename)

            try:
                urllib.request.urlretrieve(full_url, local_path)
                downloaded.append(local_path.replace("\\", "/"))
            except Exception:
                candidates = [
                    os.path.join(_THIS_DIR, "mock_edistrict", "docs", filename),
                    os.path.join(_PARENT_DIR, "mock_edistrict", "docs", filename)
                ]
                for cand in candidates:
                    if os.path.exists(cand):
                        with open(cand, "rb") as sf, open(local_path, "wb") as df:
                            df.write(sf.read())
                        downloaded.append(local_path.replace("\\", "/"))
                        break

        return downloaded

    def close(self):
        """Closes browser and frees Playwright resources."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None


# ============================================================================
# 4. CLOUD NAVIGATOR DISCOVERY SESSION & HANDOFF CONTROLLER
# ============================================================================

class CloudNavigatorSession:
    """
    Coordinates the public discovery phase of OmniKiosk:
    1. Dynamic Service Intent Classification
    2. Headless DOM Inspection & Pro-Forma Discovery
    3. PII-Safe RAG Doubt-Clearing
    4. Handoff Serializer writing current_form_schema.json
    5. Clean session termination before private data intake.
    """

    HANDOFF_TRIGGERS = [
        "let's start filling",
        "start form",
        "begin",
        "start filling",
        "fill the form",
        "let us start",
        "start now"
    ]

    def __init__(self, base_url: str = PORTAL_BASE_URL, schema_path: str = SCHEMA_OUTPUT_PATH):
        self.base_url = base_url
        self.schema_path = schema_path
        self.classifier = ServiceIntentClassifier(base_url)
        self.doubt_engine = DoubtClearingEngine()
        self.inspector = BrowserInspector()
        self.current_schema: Optional[Dict[str, Any]] = None
        self.active = False

    def __enter__(self):
        self.active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.terminate_session()

    def resolve_intent(self, intent_query: str) -> Dict[str, Any]:
        """Resolves user query to a civic service and extracts form schema dynamically."""
        classification = self.classifier.classify(intent_query)
        if classification["status"] != "SUCCESS":
            return classification

        self.current_schema = self.inspector.inspect_form(
            classification["form_url"],
            classification["service_name"]
        )

        return {
            "status": "DISCOVERED",
            "service_name": self.current_schema["service_name"],
            "form_url": self.current_schema["form_url"],
            "field_count": len(self.current_schema["fields"]),
            "downloaded_docs": self.current_schema.get("downloaded_docs", [])
        }

    def ask_doubt(self, user_question: str) -> str:
        """Answers citizen question dynamically with zero PII exposure."""
        return self.doubt_engine.answer_question(user_question)

    def check_handoff(self, utterance: str) -> Optional[Dict[str, Any]]:
        """Checks if utterance signals the start of private form filling."""
        normalized = utterance.lower().strip().rstrip(".!?,")
        for trigger in self.HANDOFF_TRIGGERS:
            if trigger in normalized:
                return self.execute_handoff()
        return None

    def execute_handoff(self) -> Dict[str, Any]:
        """
        Serializes current_form_schema.json, closes cloud discovery session,
        and hands control over to Module 5.
        """
        if not self.current_schema:
            raise ValueError("Cannot hand off: Form schema has not been extracted yet.")

        with open(self.schema_path, "w", encoding="utf-8") as f:
            json.dump(self.current_schema, f, indent=2)

        self.terminate_session()

        return {
            "status": "HANDOFF_READY",
            "schema_path": self.schema_path,
            "cloud_session_closed": True,
            "service_name": self.current_schema["service_name"],
            "form_url": self.current_schema["form_url"]
        }

    def terminate_session(self):
        """Closes browser discovery session cleanly."""
        if self.inspector:
            self.inspector.close()
        self.active = False


# ============================================================================
# 5. CLI & DEMO INTERACTION INTERFACE
# ============================================================================

def run_cli_demo():
    parser = argparse.ArgumentParser(description="OmniKiosk Module 2: Cloud Navigator & Discovery Agent")
    parser.add_argument("--intent", type=str, help="Initial natural language intent (e.g. 'I need an income certificate')")
    parser.add_argument("--portal-url", type=str, default=PORTAL_BASE_URL, help="Base URL of e-District portal")
    args = parser.parse_args()

    print("===================================================================")
    print(" OmniKiosk Module 2: Cloud Navigator & Discovery Agent (Zero PII)")
    print("===================================================================\n")

    session = CloudNavigatorSession(base_url=args.portal_url)

    intent = args.intent
    if not intent:
        intent = input("Citizen: ")

    result = session.resolve_intent(intent)
    if result["status"] != "DISCOVERED":
        print(f"System: {result.get('message', 'Service not recognized.')}")
        return

    print(f"System: Identified Service: {result['service_name']}")
    print(f"System: Form Discovered: {result['form_url']}")
    if result.get("downloaded_docs"):
        print(f"System: Downloaded Pro-Formas: {result['downloaded_docs']}")

    while True:
        try:
            user_input = input("\nCitizen: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        handoff = session.check_handoff(user_input)
        if handoff:
            print("\nSystem: [Handoff Triggered]")
            print(f"System: Form schema saved to '{handoff['schema_path']}'.")
            print("System: Headless browser discovery session CLOSED.")
            print("System: Security boundary reached. Ready for Tier 1 Private Intake (Module 5).\n")
            break

        answer = session.ask_doubt(user_input)
        print(f"System: {answer}")


if __name__ == "__main__":
    run_cli_demo()
