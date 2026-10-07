"""Business review triggers: observations never become legal eligibility or execution."""

from datetime import UTC, date, datetime

from app.domain.imports import money_paise, money_string

ACCEPTED = {"EXACT_MATCH", "REVIEW_ACCEPTED"}


def review_time(value):
    return int(datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC).timestamp())


def case_review(case, invoice):
    facts = case["facts"]
    missing = case["missing_facts"]
    kind = case["kind"]
    notes = list(missing)
    limitations = []
    proposed = None
    remaining = None
    if kind in {"MSME_REVIEW", "RULE37_REVIEW"}:
        if facts.get("amount_paid") is not None:
            remaining = money_string(
                money_paise(invoice["gross_total"], "gross_total")
                - money_paise(facts["amount_paid"], "gross_total")
            )
        else:
            notes.append("payment_balance_unknown")
    if kind == "RULE37A_REVIEW":
        claim, reversal = facts.get("original_claim_amount"), facts.get("reversal_amount")
        observed_today = datetime.now(UTC).date().isoformat()
        tax_fields = ("cgst", "sgst", "igst", "cess")
        tax_complete = all(invoice.get(field) is not None for field in tax_fields)
        if not tax_complete:
            notes.append("recorded_tax_incomplete")
        if (
            tax_complete
            and invoice.get("document_type") != "CREDIT_NOTE"
            and not missing
            and claim is not None
            and reversal is not None
            and money_paise(claim, "gross_total") > 0
            and 0 < money_paise(reversal, "gross_total") <= money_paise(claim, "gross_total")
            and money_paise(reversal, "gross_total") <= money_paise(case["amount"], "gross_total")
            and money_paise(claim, "gross_total")
            <= sum(money_paise(invoice.get(field, "0.00"), "gross_total") for field in tax_fields)
            and facts.get("original_claim_period", "9999-99") <= facts.get("reversal_period", "")
            and facts.get("reversal_period", "9999-99") <= observed_today[:7]
            and (facts.get("filing_observed_on") or "9999-99-99") <= observed_today
            and facts.get("supplier_return_period", "9999-99")
            <= (facts.get("filing_observed_on") or "")[:7]
            and facts.get("supplier_return_status") == "FILED"
        ):
            proposed = reversal
        else:
            notes.append("reclaim_conditions_require_evidence_review")
    if kind == "IRN_REVIEW":
        limitations.append("government_authenticity_unverified")
    if kind == "NOTICE_REVIEW":
        limitations.append("response_preparation_not_submission")
    return {
        "missing_facts": sorted(set(notes)),
        "limitations": limitations,
        "remaining_balance": remaining,
        "proposed_reclaim_amount": proposed,
        "reclaim_candidate": proposed is not None,
        "legal_eligibility": "NOT_DETERMINED",
        "government_verification": "NOT_IMPLEMENTED",
        "filing_execution": "NOT_IMPLEMENTED",
        "irn_observation": case["irn_observation"] if kind == "IRN_REVIEW" else None,
    }
