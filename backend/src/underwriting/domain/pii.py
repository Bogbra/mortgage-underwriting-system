"""PII redaction as a pluggable boundary control.

Design note (see docs/adr/0004): sanitization happens once, on the
*applicant_data -> sanitized_data* boundary, before any field reaches a
prompt, a vector store query, or a log line. Nothing downstream is trusted to
re-sanitize. The default implementation is deterministic, offline, and rule
based on purpose — it must work without network access or a model call and
must never fail open. A statistical NER engine (e.g. Presidio) can be dropped
in behind the same `PIIRedactor` protocol for messier free-text fields
without touching a single call site.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

_SSN_RE = re.compile(r"\d{3}-?\d{2}-?(\d{4})")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_TAIL_RE = re.compile(r"(\d{4})\D*$")

REDACTABLE_TOP_LEVEL_FIELDS = ("name", "address", "email")


class PIIRedactor(Protocol):
    """Contract any sanitizer implementation must satisfy."""

    def redact(self, data: dict[str, Any]) -> dict[str, Any]: ...


class RuleBasedPIIRedactor:
    """Default redactor: field-name aware + pattern-based fallback.

    Structured PII (ssn, phone, name, address, email) is redacted by field
    name because that is unambiguous and cheap. Free-text fields (e.g.
    underwriter notes, deposit memos) are scanned with regexes for SSNs and
    emails that may have been typed into the wrong box.
    """

    def redact(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._walk(data)

    def _walk(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._redact_field(key, val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._walk(item) for item in value]
        return value

    def _redact_field(self, key: str, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return self._walk(value)
        if not isinstance(value, str):
            return value

        lower_key = key.lower()
        if lower_key == "ssn":
            return self._mask_ssn(value)
        if lower_key == "phone":
            return self._mask_tail(value, prefix="***-***-")
        if lower_key in REDACTABLE_TOP_LEVEL_FIELDS:
            return f"[{lower_key.upper()}_REDACTED]"
        return self._scrub_free_text(value)

    @staticmethod
    def _mask_ssn(ssn: str) -> str:
        match = _SSN_RE.search(ssn)
        if not match:
            return "***-**-XXXX"
        return f"***-**-{match.group(1)}"

    @staticmethod
    def _mask_tail(value: str, prefix: str, keep: int = 4) -> str:
        match = _PHONE_TAIL_RE.search(value)
        if not match:
            return f"{prefix}XXXX"
        return f"{prefix}{match.group(1)}"

    @staticmethod
    def _scrub_free_text(text: str) -> str:
        text = _SSN_RE.sub(lambda m: f"***-**-{m.group(1)}", text)
        text = _EMAIL_RE.sub("[EMAIL_REDACTED]", text)
        return text


def sanitize_applicant_data(
    data: dict[str, Any], redactor: PIIRedactor | None = None
) -> dict[str, Any]:
    """Convenience entry point used by the workflow's initialize step."""

    redactor = redactor or RuleBasedPIIRedactor()
    return redactor.redact(data)
