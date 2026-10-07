"""Independent boundaries for review triggers and deliberately non-executing commands."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.actions import ActionOutcome, ActionUpdate, Followup
from app.domain.actions import case_review, review_time
from tests.unit.test_import_parsers import ROW


def reclaim(**patch):
    facts = {
        "original_claim_period": "2024-04",
        "original_claim_amount": "180.00",
        "reversal_period": "2024-05",
        "reversal_amount": "180.00",
        "supplier_return_period": "2024-04",
        "supplier_return_status": "FILED",
        "filing_observed_on": "2024-06-01",
    } | patch
    return {"kind": "RULE37A_REVIEW", "facts": facts, "missing_facts": [], "amount": "180.00"}


def test_reclaim_is_conservative_exact_and_never_a_filing():
    review = case_review(reclaim(), ROW)
    assert review["proposed_reclaim_amount"] == "180.00"
    assert review["reclaim_candidate"] is True
    assert review["legal_eligibility"] == "NOT_DETERMINED"
    assert review["filing_execution"] == "NOT_IMPLEMENTED"
    assert case_review(reclaim(reversal_amount="0.01"), ROW)["proposed_reclaim_amount"] == "0.01"


@pytest.mark.parametrize(
    "patch",
    [
        {"original_claim_amount": None},
        {"original_claim_amount": "0.00"},
        {"reversal_amount": None},
        {"reversal_amount": "0.00"},
        {"reversal_amount": "180.01"},
        {"original_claim_amount": "181.00"},
        {"supplier_return_status": "UNKNOWN"},
        {"supplier_return_status": "NOT_FILED"},
        {"reversal_period": "2024-03"},
        {"supplier_return_period": "2024-07"},
        {"filing_observed_on": None},
        {"filing_observed_on": "2099-06-01"},
        {"reversal_period": "2099-05"},
        {"original_claim_period": "2099-04", "reversal_period": "2099-05"},
    ],
)
def test_absent_or_contradictory_reclaim_facts_do_not_become_candidates(patch):
    assert not case_review(reclaim(**patch), ROW)["reclaim_candidate"]


def test_missing_case_evidence_credit_note_and_review_amount_cap_prevent_candidates():
    assert not case_review(reclaim() | {"missing_facts": ["evidence:FILING_OBSERVATION"]}, ROW)[
        "reclaim_candidate"
    ]
    assert not case_review(reclaim(), ROW | {"document_type": "CREDIT_NOTE"})["reclaim_candidate"]
    assert not case_review(reclaim() | {"amount": "100.00"}, ROW)["reclaim_candidate"]


def test_payment_unknown_and_exact_partial_balance_do_not_guess_deadlines():
    case = {"kind": "MSME_REVIEW", "facts": {}, "missing_facts": ["acceptance_date"]}
    unknown = case_review(case, ROW)
    assert unknown["remaining_balance"] is None
    assert "payment_balance_unknown" in unknown["missing_facts"]
    assert "acceptance_date" in unknown["missing_facts"]
    paid = case_review(case | {"facts": {"amount_paid": "0.01"}}, ROW)
    assert paid["remaining_balance"] == "1179.99"
    assert "statutory_deadline" not in paid
    assert review_time("2024-06-01") == int(datetime(2024, 6, 1, tzinfo=UTC).timestamp())


@pytest.mark.parametrize(
    "model,payload",
    [
        (ActionUpdate, {"state": "AUTO_APPROVED"}),
        (ActionUpdate, {"state": "OPEN", "expected_version": True}),
        (ActionUpdate, {"state": "OPEN", "review_on": "2024-02-30"}),
        (ActionUpdate, {"state": "OPEN", "reason": "hidden\ncommand"}),
        (Followup, {"contact": "supplier", "request": "Check"}),
        (Followup, {"contact": "+919876543210", "request": "Check", "observed_on": "2024-06-01"}),
        (Followup, {"kind": "ATTEMPT_RECORDED", "contact": "+919876543210", "request": "Check"}),
        (ActionOutcome, {"kind": "REVIEW_DECISION"}),
        (ActionOutcome, {"kind": "REVIEW_DECISION", "decision": "REVIEW_ACCEPTED", "amount": 1.25}),
        (
            ActionOutcome,
            {"kind": "REVIEW_DECISION", "decision": "REVIEW_ACCEPTED", "reference": "fake"},
        ),
        (
            ActionOutcome,
            {
                "kind": "FILING_OBSERVATION",
                "reference": "fake",
                "observed_on": "2099-01-01",
                "amount": "1.00",
                "evidence_event_ids": [str(uuid4())],
            },
        ),
    ],
)
def test_invalid_command_inputs_are_rejected_before_services(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate({"expected_version": 1, "reason": "Review", **payload})


def test_markup_is_readable_text_and_duplicate_evidence_is_rejected():
    draft = Followup(
        expected_version=1,
        reason="Review",
        contact="supplier@example.com",
        request="<script>display only</script>",
    )
    assert draft.request.startswith("<script>")
    identifier = uuid4()
    with pytest.raises(ValidationError):
        ActionOutcome(
            expected_version=1,
            reason="Review",
            kind="NOTICE_SUBMISSION_OBSERVATION",
            reference="REF",
            observed_on="2024-06-01",
            evidence_event_ids=[identifier, identifier],
        )


def test_unknown_tax_components_remain_reviewable_without_a_reclaim_candidate():
    review = case_review(reclaim(), ROW | {"cess": None})
    assert not review["reclaim_candidate"]
    assert review["proposed_reclaim_amount"] is None
    assert "recorded_tax_incomplete" in review["missing_facts"]
