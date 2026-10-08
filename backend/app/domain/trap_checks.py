"""Six evidence-based review signals. These never approve credit or calculate penalties."""

import re
from datetime import date
from decimal import Decimal

SECTION16 = "https://taxinformation.cbic.gov.in/content-page/explore-act/1000285/1000001"
MSME = "https://www.msmediagra.gov.in/writereaddata/msmedact.pdf"
RULES = "https://taxinformation.cbic.gov.in/"
NOTICE = "https://gstcouncil.gov.in/sites/default/files/2024-05/gst-ct-38-2023.pdf"
RECLAIM = "https://gstcouncil.gov.in/sites/default/files/2024-05/ct26-2022.pdf"


def detect(view, facts, today=None):
    today = today or date.today()
    findings = view["findings"]
    fields = view["fields"]
    clocks = view.get("clocks", {})
    tax = view["gate"].get("recorded_tax_under_review")

    def signal(key, title, reference, source, state, reason, action, amount=None, deadline=None):
        return {
            "id": key,
            "title": title,
            "reference": reference,
            "source": source,
            "state": state,
            "reason": reason,
            "action": action,
            "recorded_amount": amount,
            "deadline": deadline,
            "review": "NEEDS_CA_REVIEW",
            "review_note": "Verify with CA. This is a saved-evidence review signal.",
        }

    gst = findings.get("gst", "MISSING")
    result = [
        signal(
            "missing_gst",
            "Check the supplier tax record",
            "CGST Section 16(2)(aa)",
            SECTION16,
            "NO_SIGNAL" if gst == "MATCHED" else "ATTENTION" if view["confirmed"] else "UNKNOWN",
            "The supplied GST evidence aligns."
            if gst == "MATCHED"
            else "The bill is not aligned with the selected GST evidence.",
            "Confirm the intended statement and ask the supplier to correct the record.",
            tax,
        )
    ]
    due = clocks.get("pay_by")
    covered = clocks.get("facts", {}).get("msme_covered")
    overdue = bool(due and date.fromisoformat(due) < today)
    remaining = view["gate"].get("remaining_amount")
    outstanding = remaining is None or Decimal(remaining) > 0
    result.append(
        signal(
            "msme_timing",
            "Review the supplier payment date",
            "MSMED Act Section 15; legacy Income-tax Act 43B(h), "
            "current-period mapping needs CA review",
            MSME,
            "ATTENTION"
            if covered is True and overdue and outstanding
            else "NO_SIGNAL"
            if covered is False
            or (due and not overdue)
            or (remaining is not None and not outstanding)
            else "UNKNOWN",
            "Review the recorded micro/small supplier classification, "
            "acceptance and written terms. There is no universal tax-penalty "
            "rate.",
            "Check payment timing and deduction treatment with your CA before"
            " deciding to hold money.",
            remaining,
            due,
        )
    )
    reversal = facts.get("reversed_on")
    filed = facts.get("supplier_3b_filed_on")
    unfiled = facts.get("supplier_3b_unfiled_as_of")
    claimed_on = clocks.get("facts", {}).get("claimed_on")
    reversal_deadline = None
    if facts.get("credit_claimed") is True and claimed_on and unfiled and gst == "MATCHED":
        claim_date = date.fromisoformat(claimed_on)
        following_year = claim_date.year + (1 if claim_date.month >= 4 else 0)
        if date.fromisoformat(unfiled) >= date(following_year, 9, 30):
            reversal_deadline = date(following_year, 11, 30).isoformat()
    result.append(
        signal(
            "reclaim",
            "Do not forget a recorded credit reversal",
            "CGST Rule 37A",
            RECLAIM,
            "ATTENTION"
            if (reversal and filed) or (reversal_deadline and not reversal)
            else "MONITOR"
            if reversal or (facts.get("credit_claimed") and unfiled)
            else "UNKNOWN",
            "A reversal and later supplier-filing observation need reclaim review."
            if reversal and filed
            else "Credit-claim, reversal and supplier filing observations may be incomplete.",
            "Retain the actual filing/reversal evidence. Where the claim year and September "
            "filing observation apply, review reversal by 30 November with your CA; "
            "later filing may allow re-availment.",
            facts.get("reversed_tax"),
            reversal_deadline,
        )
    )
    required = fields.get("irn_required")
    irn = fields.get("irn") or ""
    state = (
        "ATTENTION"
        if required is True and not re.fullmatch(r"[a-fA-F0-9]{64}", irn)
        else "FORMAT_ONLY"
        if required is True
        else "NO_SIGNAL"
        if required is False
        else "UNKNOWN"
    )
    result.append(
        signal(
            "irn",
            "Check the e-invoice reference",
            "CGST Rule 48(4)",
            RULES,
            state,
            "Reference format does not establish government authenticity or applicability.",
            "Confirm applicability and authenticate the IRN through an authorized source.",
        )
    )
    notice = facts.get("notice_reference")
    deadline = facts.get("notice_response_due_on")
    answered = facts.get("notice_response_recorded")
    result.append(
        signal(
            "notice",
            "Review the actual notice response date",
            "CGST Rule 88D / DRC-01C",
            NOTICE,
            "NO_SIGNAL" if notice and answered is True else "ATTENTION" if notice else "UNKNOWN",
            "Recorded notice response evidence is available."
            if notice and answered is True
            else "A notice needs its own reference, deadline and response facts; "
            "no bank freeze is inferred.",
            "Open the notice evidence and prepare a reviewed response. Nothing is submitted here.",
            None,
            deadline,
        )
    )
    deadline = facts.get("credit_review_due_on")
    result.append(
        signal(
            "credit_deadline",
            "Review credit before its actual deadline",
            "CGST Section 16(4)",
            SECTION16,
            "ATTENTION"
            if deadline and date.fromisoformat(deadline) <= today
            else "MONITOR"
            if deadline
            else "UNKNOWN",
            "The supplied credit-review date needs attention."
            if deadline
            else "No CA-confirmed credit-review deadline has been recorded.",
            "Resolve ambiguous matches and confirm the applicable "
            "financial-year deadline and exceptions.",
            tax,
            deadline,
        )
    )
    return result
