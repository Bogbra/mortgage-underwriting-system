from underwriting.domain.pii import RuleBasedPIIRedactor, sanitize_applicant_data


def test_ssn_is_masked_but_last_four_kept():
    out = sanitize_applicant_data({"ssn": "123-45-6789"})
    assert out["ssn"] == "***-**-6789"


def test_ssn_without_dashes_is_masked():
    out = sanitize_applicant_data({"ssn": "123456789"})
    assert out["ssn"] == "***-**-6789"


def test_name_address_email_are_redacted():
    out = sanitize_applicant_data(
        {"name": "Sarah Johnson", "address": "12 Main St", "email": "sarah@example.com"}
    )
    assert out["name"] == "[NAME_REDACTED]"
    assert out["address"] == "[ADDRESS_REDACTED]"
    assert out["email"] == "[EMAIL_REDACTED]"


def test_phone_keeps_last_four_digits_only():
    out = sanitize_applicant_data({"phone": "555-123-4567"})
    assert out["phone"] == "***-***-4567"


def test_nested_structures_are_redacted_recursively():
    out = sanitize_applicant_data(
        {
            "case_id": "CASE-001",
            "name": "Michael Chen",
            "assets": {
                "recent_deposits": [{"amount": 5000, "date": "2026-01-01"}],
            },
            "notes": "Applicant SSN 987-65-4321 confirmed by phone.",
        }
    )
    assert out["case_id"] == "CASE-001"  # non-PII field untouched
    assert out["assets"]["recent_deposits"][0]["amount"] == 5000  # numeric data untouched
    assert "987-65-4321" not in out["notes"]
    assert "***-**-4321" in out["notes"]


def test_custom_redactor_can_be_injected():
    class NullRedactor:
        def redact(self, data):
            return data

    out = sanitize_applicant_data({"ssn": "123-45-6789"}, redactor=NullRedactor())
    assert out["ssn"] == "123-45-6789"


def test_default_redactor_is_deterministic():
    redactor = RuleBasedPIIRedactor()
    data = {"ssn": "111-22-3333", "phone": "222-333-4444"}
    assert redactor.redact(data) == redactor.redact(data)
