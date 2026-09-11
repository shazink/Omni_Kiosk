"""
Request Router for OmniKiosk Dual-Tier Architecture:
- Tier 1: Local On-Device processing for PII and sensitive data intake.
- Tier 2: Cloud / Public knowledge discovery and generic doubt-clearing.
"""

import re
from typing import Dict, Any, Tuple


class RequestRouter:
    """Dispatches queries and actions to either Tier 1 (Local) or Tier 2 (Cloud/Public)."""

    # Regex patterns for detecting citizen PII
    AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b|\b\d{12}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+91[- ]?)?[6-9]\d{9}\b")
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    BANK_ACCOUNT_PATTERN = re.compile(r"\b\d{9,18}\b")
    IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

    @classmethod
    def sanitize_pii(cls, text: str) -> Tuple[str, bool]:
        """
        Sanitizes PII from user text prior to any Tier 2 / Cloud interaction.
        Returns: (sanitized_text, had_pii_flag)
        """
        sanitized = text
        had_pii = False

        if cls.AADHAAR_PATTERN.search(sanitized):
            sanitized = cls.AADHAAR_PATTERN.sub("[REDACTED_AADHAAR]", sanitized)
            had_pii = True

        if cls.PHONE_PATTERN.search(sanitized):
            sanitized = cls.PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
            had_pii = True

        if cls.EMAIL_PATTERN.search(sanitized):
            sanitized = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
            had_pii = True

        if cls.IFSC_PATTERN.search(sanitized):
            sanitized = cls.IFSC_PATTERN.sub("[REDACTED_IFSC]", sanitized)
            had_pii = True

        return sanitized, had_pii

    @classmethod
    def route_request(cls, query: str, current_phase: str = "DISCOVERY") -> Dict[str, Any]:
        """
        Determines whether the query belongs to Tier 1 (Local) or Tier 2 (Cloud/Public).
        """
        sanitized_text, had_pii = cls.sanitize_pii(query)

        # If citizen is in form filling phase or transmitting personal identifiers
        if current_phase == "FORM_FILLING" or had_pii:
            return {
                "tier": "TIER_1_LOCAL",
                "target": "local_form_filler.EdgeSLM",
                "sanitized_text": sanitized_text,
                "had_pii": had_pii,
                "reason": "Personal Identifiable Information (PII) or form data intake routed to on-device SLM."
            }

        return {
            "tier": "TIER_2_CLOUD_OR_PUBLIC_KB",
            "target": "cloud_navigator.DoubtClearingEngine",
            "sanitized_text": sanitized_text,
            "had_pii": False,
            "reason": "Public informational query or navigation intent routed safely."
        }
