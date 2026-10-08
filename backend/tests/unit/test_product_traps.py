from datetime import date

from app.domain.trap_checks import detect


def view():
    return {
        "confirmed": True,
        "fields": {"irn_required": True, "irn": ""},
        "findings": {"gst": "MISSING"},
        "clocks": {"pay_by": "2024-06-15", "facts": {"msme_covered": True}},
        "gate": {"recorded_tax_under_review": "18000.00", "remaining_amount": "118000.00"},
    }


def test_six_traps_do_not_invent_loss_or_eligibility():
    facts = {
        "credit_claimed": True,
        "reversed_on": "2024-05-20",
        "reversed_tax": "18000.00",
        "supplier_3b_filed_on": "2024-06-01",
        "notice_reference": "ACTUAL-NOTICE",
        "notice_response_due_on": "2024-06-07",
        "notice_response_recorded": False,
        "credit_review_due_on": "2024-06-20",
    }
    traps = detect(view(), facts, date(2024, 7, 1))
    assert len(traps) == 6 and len({t["id"] for t in traps}) == 6
    assert all(t["state"] == "ATTENTION" for t in traps)
    assert all(
        t["review"] == "NEEDS_CA_REVIEW" and t["source"].startswith("https://") for t in traps
    )
    assert traps[0]["recorded_amount"] == "18000.00"
    assert traps[1]["recorded_amount"] == "118000.00"  # payment balance, never tax penalty
    assert traps[2]["recorded_amount"] == "18000.00"
    assert traps[4]["deadline"] == "2024-06-07"


def test_unknown_is_not_zero_and_irn_is_format_only():
    v = view()
    v["confirmed"] = False
    v["gate"]["recorded_tax_under_review"] = None
    v["clocks"] = {}
    v["fields"] = {"irn_required": None}
    traps = detect(v, {}, date(2024, 7, 1))
    assert all(t["state"] == "UNKNOWN" for t in traps)
    assert traps[0]["recorded_amount"] is None
    v["fields"] = {"irn_required": True, "irn": "a" * 64}
    assert detect(v, {})[3]["state"] == "FORMAT_ONLY"


def test_recorded_response_and_uncovered_supplier_clear_only_their_signal():
    v = view()
    v["findings"]["gst"] = "MATCHED"
    v["clocks"]["facts"]["msme_covered"] = False
    traps = detect(v, {"notice_reference": "REAL", "notice_response_recorded": True})
    assert traps[0]["state"] == traps[1]["state"] == traps[4]["state"] == "NO_SIGNAL"
    assert traps[2]["state"] == "UNKNOWN"


def test_rule37a_deadline_uses_claim_year_and_actual_september_observation():
    v = view()
    v["findings"]["gst"] = "MATCHED"
    v["clocks"]["facts"]["claimed_on"] = "2024-05-01"
    facts = {"credit_claimed": True, "supplier_3b_unfiled_as_of": "2025-09-30"}
    signal = detect(v, facts, date(2025, 10, 1))[2]
    assert signal["deadline"] == "2025-11-30" and signal["state"] == "ATTENTION"
    facts["supplier_3b_unfiled_as_of"] = "2025-09-29"
    assert detect(v, facts, date(2025, 10, 1))[2]["deadline"] is None
    v["clocks"]["facts"]["claimed_on"] = "2025-02-01"
    facts["supplier_3b_unfiled_as_of"] = "2025-09-30"
    assert detect(v, facts, date(2025, 10, 1))[2]["deadline"] == "2025-11-30"
    v["findings"]["gst"] = "MISSING"
    assert detect(v, facts, date(2025, 10, 1))[2]["deadline"] is None
