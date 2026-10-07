"""Pure evidence completeness and integer allocation rules."""

import re

from pydantic import ValidationError

from app.contracts.workflows import FACT_MODELS
from app.domain.imports import money_paise
from app.errors import APIError


def validate_facts(kind, facts, gross=None):
    try:
        result = FACT_MODELS[kind].model_validate(facts).model_dump(mode="json")
        if len(set(result["observation_refs"])) != len(result["observation_refs"]):
            raise ValueError("Duplicate observation")
        paid = result.get("amount_paid")
        if paid is not None and gross is not None and money_paise(paid, "gross_total") > gross:
            raise ValueError("Paid amount exceeds source gross")
        claim, reversal = result.get("original_claim_amount"), result.get("reversal_amount")
        if (
            claim is not None
            and reversal is not None
            and money_paise(reversal, "gross_total") > money_paise(claim, "gross_total")
        ):
            raise ValueError("Reversal exceeds recorded original claim")
        return result
    except (ValidationError, ValueError, KeyError):
        raise APIError(422, "INVALID_FACTS", "Facts are invalid for this case kind.") from None


def missing_facts(kind, facts, event_kinds):
    required = {
        "MSME_REVIEW": [
            "acceptance_date",
            "agreed_credit_days",
            "amount_paid",
            "payment_observed_on",
        ],
        "RULE37_REVIEW": [
            "original_claim_period",
            "original_claim_amount",
            "amount_paid",
            "payment_observed_on",
        ],
        "RULE37A_REVIEW": [
            "original_claim_period",
            "original_claim_amount",
            "reversal_period",
            "reversal_amount",
            "supplier_return_period",
            "filing_observed_on",
        ],
        "IRN_REVIEW": ["irn"],
        "NOTICE_REVIEW": ["notice_reference", "notice_date", "response_due_date"],
    }[kind]
    missing = [name for name in required if facts.get(name) in (None, "")]
    if kind == "MSME_REVIEW" and facts["supplier_classification"] == "UNKNOWN":
        missing.append("supplier_classification")
    if kind == "RULE37A_REVIEW" and facts["supplier_return_status"] == "UNKNOWN":
        missing.append("supplier_return_status")
    if kind == "IRN_REVIEW":
        if facts["applicability"] == "UNKNOWN":
            missing.append("applicability")
        if facts.get("irn") and not re.fullmatch(r"[0-9a-fA-F]{64}", facts["irn"]):
            missing.append("irn_format")
    needed = {
        "MSME_REVIEW": {"ACCEPTANCE_OBSERVATION", "PAYMENT_OBSERVATION"},
        "RULE37_REVIEW": {"PAYMENT_OBSERVATION"},
        "RULE37A_REVIEW": {"FILING_OBSERVATION"},
        "IRN_REVIEW": {"IRN_OBSERVATION"},
        "NOTICE_REVIEW": {"DOCUMENT"},
    }[kind]
    missing += ["evidence:" + name for name in sorted(needed - set(event_kinds))]
    return missing


def allocations_within_balances(allocations, balances):
    totals = {}
    for item in allocations:
        document = item["document_id"]
        if document not in balances:
            raise APIError(422, "INVALID_ALLOCATION", "Every allocation needs a recorded balance.")
        totals[document] = totals.get(document, 0) + money_paise(item["amount"], "gross_total")
    if set(totals) != set(balances) or any(totals[key] > balances[key] for key in totals):
        raise APIError(422, "BALANCE_EXCEEDED", "Allocations exceed or omit recorded balances.")
    return sum(totals.values())
