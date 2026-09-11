"""
Quick diagnostic test to verify Groq API connectivity and response with OmniKiosk guardrails.
"""

import json
import os
import urllib.request
from .cloud_navigator import DoubtClearingEngine, PIISanitizer, load_env

load_env()

groq_key = os.environ.get("GROQ_API_KEY", "").strip()
groq_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
provider = os.environ.get("LLM_PROVIDER", "groq")

print(f"Provider Configured : {provider}")
print(f"Groq Model          : {groq_model}")
print(f"Groq Key Loaded     : {groq_key[:8]}...{groq_key[-4:] if len(groq_key) > 12 else ''}")

engine = DoubtClearingEngine()

test_questions = [
    "What counts as annual income for my application?",
    "How many days does it take to get the certificate?",
    "My Aadhaar is 987654321098. Can I apply if I do not have a salary slip?"
]

print("\n--- Running Live Doubt-Clearing Tests ---\n")

for i, q in enumerate(test_questions, 1):
    print(f"[Query {i}] Citizen asks: \"{q}\"")
    sanitized_q, had_pii = PIISanitizer.sanitize(q)
    if had_pii:
        print(f"  [Security Guardrail] PII Detected & Scrubbed -> \"{sanitized_q}\"")
    
    answer = engine.answer_question(q)
    print(f"  [AI Response]       : \"{answer}\"")
    sentences = [s.strip() for s in answer.split(".") if s.strip()]
    print(f"  [Sentence Count]    : {len(sentences)} (Max allowed: 2)")
    print()

print("Groq API Diagnostic Check Completed Successfully!")
