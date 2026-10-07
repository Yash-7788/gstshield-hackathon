"""Independent expectations for money, identity gates and contested candidate graphs."""

from copy import deepcopy
from itertools import permutations

import pytest

from app.domain.imports import ParseFailure, canonical_row
from app.domain.reconciliation import reconcile, summarize
from tests.unit.test_import_parsers import ROW

POLICY = {
    "amount_tolerance": "0.01",
    "fuzzy_threshold": "88",
    "fuzzy_gap": "5",
    "max_candidates": 10000,
    "max_pairs": 4000000,
}


def record(number="INV-001", *, row=1, kind="PURCHASE", **changes):
    raw = ROW | {"invoice_number": number, "voucher_id": f"V{row}"} | changes
    return canonical_row(raw, {field: field for field in raw}, ROW["recipient_gstin"], kind, row)


def output(purchases, portals, policy=None):
    return reconcile(purchases, portals, POLICY | (policy or {}))["results"]


def test_exact_identity_and_one_paise_tolerance_preserve_signed_differences():
    result = output(
        [record(" inv-001 ")],
        [record("INV-001", kind="PORTAL_2B", cgst="90.01", gross_total="1180.01")],
    )[0]
    assert result["status"] == "EXACT_MATCH"
    assert result["assigned_portal_row"] == 1
    assert result["candidates"][0]["amount_differences"]["cgst"] == "-0.01"
    assert "WITHIN_AMOUNT_TOLERANCE" in result["reason_codes"]
    result = output([record()], [record(kind="PORTAL_2B", cgst="90.02", gross_total="1180.02")])[0]
    assert result["status"] == "AMOUNT_MISMATCH"
    assert not result["candidates"][0]["hard_gates_passed"]


@pytest.mark.parametrize(
    "changes",
    [
        {"supplier_gstin": "27LMNOP1234F1Z5"},
        {"recipient_gstin": "27LMNOP1234F1Z5"},
        {"invoice_date": "2024-04-11"},
        {"document_type": "DEBIT_NOTE"},
    ],
)
def test_hard_identity_gates_cannot_be_overcome_by_score(changes):
    portal = record(kind="PORTAL_2B", **changes)
    # For recipient gate, construct an accepted row from another registration.
    portal["accepted"] = True
    portal["canonical"].update(changes)
    assert output([record()], [portal])[0]["status"] == "MISSING_IN_SNAPSHOT"


def test_same_number_other_year_is_not_a_match():
    result = output([record()], [record(kind="PORTAL_2B", invoice_date="2023-04-10")])[0]
    assert result["status"] == "MISSING_IN_SNAPSHOT"
    assert result["reason_codes"] == ["SAME_NUMBER_DIFFERENT_YEAR"]


def test_fuzzy_separator_match_is_only_a_suggestion_and_never_assigned():
    result = output([record("INV/001")], [record("INV-001", kind="PORTAL_2B")])[0]
    assert result["status"] == "FUZZY_SUGGESTION"
    assert result["assigned_portal_row"] is None
    assert result["candidates"][0]["score"] == "100.00"
    assert result["candidates"][0]["hard_gates_passed"]
    # Leading zeroes and explicit year digits cannot be erased into exact matches.
    for number in ("INV-01", "INV-2024-001"):
        assert output([record(number)], [record(kind="PORTAL_2B")])[0]["status"] != "EXACT_MATCH"


@pytest.mark.parametrize("side", ["purchase", "portal"])
def test_duplicate_identity_quarantines_every_copy_before_assignment(side):
    purchases, portals = [record()], [record(kind="PORTAL_2B")]
    target = purchases if side == "purchase" else portals
    copy = deepcopy(target[0])
    copy["row_number"] = 2
    target.append(copy)
    results = output(purchases, portals)
    assert all(result["status"] == "AMBIGUOUS" for result in results)
    assert all(result["assigned_portal_row"] is None for result in results)
    assert all(
        not candidate["hard_gates_passed"]
        for result in results
        for candidate in result["candidates"]
    )


def test_rejected_duplicate_and_unknown_evidence_cannot_create_clean_exact_match():
    rejected = record(kind="PORTAL_2B", row=2, gross_total="1.00")
    assert not rejected["accepted"]
    assert output([record()], [record(kind="PORTAL_2B"), rejected])[0]["status"] == "AMBIGUOUS"
    for kind in ("PURCHASE", "PORTAL_2B"):
        left, right = record(), record(kind="PORTAL_2B")
        unknown = record(kind=kind, cess="")
        assert unknown["accepted"] and unknown["amounts"]["total_tax"] is None
        result = output(
            [unknown if kind == "PURCHASE" else left], [unknown if kind == "PORTAL_2B" else right]
        )[0]
        assert result["status"] == "EVIDENCE_INCOMPLETE"
        assert result["assigned_portal_row"] is None


def test_low_gap_and_shared_candidates_are_permutation_invariant():
    purchases = [record("INV/001", row=1), record("INV.001", row=2)]
    portals = [
        record("INV-001", row=1, kind="PORTAL_2B"),
        record("INV_001", row=2, kind="PORTAL_2B"),
    ]
    for left in permutations(purchases):
        for right in permutations(portals):
            results = output(list(left), list(right))
            assert all(result["status"] == "AMBIGUOUS" for result in results)
            assert all("MULTIPLE_CANDIDATES" in result["reason_codes"] for result in results)
            assert all(result["assigned_portal_row"] is None for result in results)


def test_exact_assignment_cannot_be_stolen_by_a_fuzzy_candidate():
    for left in permutations([record("INV-001", row=1), record("INV/001", row=2)]):
        results = {
            item["source_row_number"]: item
            for item in output(list(left), [record(kind="PORTAL_2B")])
        }
        assert results[1]["status"] == "EXACT_MATCH"
        assert results[2]["status"] == "AMBIGUOUS"
        assert not results[2]["candidates"][0]["hard_gates_passed"]


def test_pair_and_candidate_limits_fail_instead_of_truncating_ambiguity():
    with pytest.raises(ParseFailure, match="MATCH_CANDIDATE_LIMIT"):
        output(
            [record()],
            [record(kind="PORTAL_2B"), record(kind="PORTAL_2B", row=2)],
            {"max_candidates": 1},
        )
    with pytest.raises(ParseFailure, match="MATCH_PAIR_LIMIT"):
        output(
            [record("INV/001")],
            [record(kind="PORTAL_2B"), record(kind="PORTAL_2B", row=2)],
            {"max_pairs": 1},
        )


def test_independent_summary_exact_large_money_unknown_and_credit_note_separation():
    rows = [
        {"status": "EXACT_MATCH", "document_type": "INVOICE", "total_tax": 18000},
        {"status": "AMOUNT_MISMATCH", "document_type": "INVOICE", "total_tax": 18000},
        {"status": "MISSING_IN_SNAPSHOT", "document_type": "DEBIT_NOTE", "total_tax": 101},
        {"status": "REJECTED", "document_type": "CREDIT_NOTE", "total_tax": 999},
        {"status": "EVIDENCE_INCOMPLETE", "document_type": "INVOICE", "total_tax": None},
        {"status": "EVIDENCE_INCOMPLETE", "document_type": "CREDIT_NOTE", "total_tax": None},
        {"status": "AMBIGUOUS", "document_type": "INVOICE", "total_tax": 9999999999999999},
    ]
    summary = summarize(rows)
    assert summary["accepted_purchase_rows"] == 7
    assert sum(summary["counts"].values()) == 7 and len(summary["counts"]) == 8
    assert summary["tax_exposure_review"] == "100000000000181.00"
    assert summary["credit_note_tax_review"] == "9.99"
    assert summary["unknown_tax_exposure_rows"] == summary["unknown_credit_note_tax_rows"] == 1


def test_invalid_same_number_snapshot_row_retains_evidence_uncertainty():
    result = output([record()], [record(kind="PORTAL_2B", invoice_date="bad-date")])[0]
    assert result["status"] == "EVIDENCE_INCOMPLETE"
    assert result["reason_codes"] == ["PORTAL_ROW_REJECTED"]
    assert result["candidates"] == [] and result["assigned_portal_row"] is None


def test_score_rounding_cannot_raise_a_threshold_or_inflate_the_score_gap(monkeypatch):
    monkeypatch.setattr("app.domain.reconciliation.ratio", lambda left, right: 87.999999)
    assert (
        output([record("INV/001")], [record(kind="PORTAL_2B")])[0]["status"]
        == "MISSING_IN_SNAPSHOT"
    )

    def scores(left, right):
        return 100.0 if right == "INV001" else 95.001

    monkeypatch.setattr("app.domain.reconciliation.ratio", scores)
    result = output(
        [record("INV/001")], [record(kind="PORTAL_2B"), record("INV002", row=2, kind="PORTAL_2B")]
    )[0]
    assert result["status"] == "AMBIGUOUS" and "LOW_SCORE_GAP" in result["reason_codes"]
    assert [candidate["score"] for candidate in result["candidates"]] == ["100.00", "95.00"]
    assert all("score_raw" not in candidate for candidate in result["candidates"])


def test_components_cannot_cancel_a_mismatch_behind_an_equal_tax_total():
    result = output([record()], [record(kind="PORTAL_2B", cgst="89.98", sgst="90.02")])[0]
    assert result["status"] == "AMOUNT_MISMATCH"
    assert result["candidates"][0]["amount_differences"]["cgst"] == "0.02"
    assert result["candidates"][0]["amount_differences"]["sgst"] == "-0.02"


@pytest.mark.parametrize("gap", ["0", "5"])
def test_equal_top_scores_stay_ambiguous_even_with_zero_configured_gap(gap):
    result = output(
        [record("INV/001")],
        [record(kind="PORTAL_2B"), record("INV_001", row=2, kind="PORTAL_2B")],
        {"fuzzy_gap": gap},
    )[0]
    assert result["status"] == "AMBIGUOUS"
    assert result["assigned_portal_row"] is None
    assert len(result["candidates"]) == 2
    assert all(candidate["hard_gates_passed"] for candidate in result["candidates"])


def test_invoice_normalization_work_is_linear_even_when_candidate_graph_is_dense(monkeypatch):
    import hashlib

    from app.domain import reconciliation

    original = reconciliation.comparison_number
    normalized = []

    def count(value):
        normalized.append(value)
        return original(value)

    monkeypatch.setattr(reconciliation, "comparison_number", count)
    numbers = [hashlib.sha256(str(index).encode()).hexdigest()[:24] for index in range(12)]
    purchases = [record("INV/" + number, row=index + 1) for index, number in enumerate(numbers)]
    portals = [
        record("INV-" + number, row=index + 1, kind="PORTAL_2B")
        for index, number in enumerate(numbers)
    ]
    result = reconciliation.reconcile(purchases, portals, POLICY)
    assert result["compared_pairs"] == 144
    assert result["candidate_count"] == 12
    assert all(row["status"] == "FUZZY_SUGGESTION" for row in result["results"])
    assert len(normalized) <= len(purchases) + len(portals)


@pytest.mark.parametrize("raw_score", [0.0, 87.999999, 88.0, 88.009999, 90.0, 100.0])
@pytest.mark.parametrize("threshold", ["0", "88", "88.001", "88.009"])
def test_fast_score_rejection_preserves_decimal_floor_thresholds(monkeypatch, raw_score, threshold):
    from decimal import ROUND_FLOOR, Decimal

    monkeypatch.setattr("app.domain.reconciliation.ratio", lambda left, right: raw_score)
    result = output(
        [record("INV/001")], [record(kind="PORTAL_2B")], {"fuzzy_threshold": threshold}
    )[0]
    expected = Decimal(str(raw_score)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR) >= Decimal(
        threshold
    )
    assert bool(result["candidates"]) == expected
    assert result["status"] == ("FUZZY_SUGGESTION" if expected else "MISSING_IN_SNAPSHOT")
    if expected:
        assert result["candidates"][0]["score"] == format(
            Decimal(str(raw_score)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR), ".2f"
        )
