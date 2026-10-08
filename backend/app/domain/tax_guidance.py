"""Curated review suggestions, never legal eligibility or a payable-tax engine."""

from app.domain.trap_checks import detect


def suggestions(view, facts, fingerprint):
    entries = []
    titles = {
        "missing_gst": "Check whether all eligible purchase credit is included",
        "msme_timing": "Review supplier timing before losing a deduction",
        "reclaim": "Review a possible reclaim of previously reversed credit",
        "irn": "Correct missing e-invoice evidence",
        "notice": "Prepare the notice response from saved evidence",
        "credit_deadline": "Check the credit claim before its reviewed deadline",
    }
    for trap in detect(view, facts):
        if trap["state"] == "NO_SIGNAL":
            continue
        upper = trap["recorded_amount"]
        # A payment balance is not an estimate of tax savings.
        if trap["id"] in {"msme_timing", "notice", "irn"}:
            upper = None
        entries.append(
            {
                "id": trap["id"],
                "title": titles[trap["id"]],
                "reference": trap["reference"],
                "source": trap["source"],
                "trigger": trap["reason"],
                "estimate_range": {"minimum": "0.00", "maximum": upper}
                if upper is not None
                else "UNKNOWN",
                "estimate_kind": "POTENTIAL_REVIEW_AMOUNT_NOT_PROMISED_SAVINGS",
                "deadline": trap["deadline"],
                "risk_level": "HIGH" if trap["state"] == "ATTENTION" else "NEEDS_FACTS",
                "steps": [
                    trap["action"],
                    "Confirm with your CA using the actual transaction and current rule.",
                ],
                "review": "NEEDS_CA_REVIEW",
                "fingerprint": fingerprint,
            }
        )
    if view["gate"]["recommendation"] == "PARTIAL_CONTROLLED_PAYMENT":
        entries.append(
            {
                "id": "controlled_payment",
                "title": "Review a controlled payment while tax evidence is missing",
                "reference": "CGST Section 16(2); MSMED Act Section 15",
                "source": "https://taxinformation.cbic.gov.in/",
                "trigger": view["gate"]["reason"],
                "estimate_range": "UNKNOWN",
                "estimate_kind": "NOT_A_TAX_SAVING",
                "deadline": view.get("clocks", {}).get("pay_by"),
                "risk_level": "HIGH",
                "steps": [
                    "Review supplier contract, payment timing and the retained tax amount.",
                    "Confirm with your CA. Internal retention is not a legal safe "
                    "harbour or bank escrow.",
                ],
                "review": "NEEDS_CA_REVIEW",
                "fingerprint": fingerprint,
            }
        )
    return entries
