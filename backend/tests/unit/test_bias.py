from underwriting.domain.bias import scan_for_bias_signals, scan_many


def test_clean_analysis_has_no_flags():
    text = "Credit score of 760 places the applicant in the excellent tier, no derogatory items."
    assert scan_for_bias_signals(text, applicant_data={}) == []


def test_flags_protected_characteristic_mention():
    text = "Given the applicant's age and marital status, we recommend caution."
    flags = scan_for_bias_signals(text, applicant_data={})
    codes = {f.code for f in flags}
    assert "protected_characteristic_mentioned" in codes
    assert len(flags) == 2  # age + marital status


def test_word_boundary_avoids_false_positive_substring():
    # "manager" contains no protected term as a substring match issue,
    # but "ageless" should not falsely trigger on "age" without a boundary.
    text = "The applicant works as a property manager and enjoys ageless design."
    flags = scan_for_bias_signals(text, applicant_data={})
    assert flags == []


def test_geographic_proxy_flag_requires_both_zip_and_language():
    text = "The property is in a desirable neighborhood."
    no_zip = scan_for_bias_signals(text, applicant_data={})
    assert all(f.code != "potential_geographic_proxy" for f in no_zip)

    with_zip = scan_for_bias_signals(text, applicant_data={"zip": "10001"})
    codes = {f.code for f in with_zip}
    assert "potential_geographic_proxy" in codes


def test_scan_many_aggregates_across_agents_and_skips_none():
    analyses = {
        "credit": "Solid credit history, low risk.",
        "income": None,
        "asset": "Applicant's religion was not a factor but is mentioned here.",
    }
    flags = scan_many(analyses, applicant_data={})
    assert len(flags) == 1
    assert flags[0].code == "protected_characteristic_mentioned"
