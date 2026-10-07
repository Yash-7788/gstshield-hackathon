"""Report escaping, arithmetic and fact validation independent of services."""

import csv
import io

import pytest
from pypdf import PdfReader

from app.adapters.reports import ReportFailure, csv_bytes, csv_cell, generate
from app.domain.workflows import allocations_within_balances, missing_facts, validate_facts
from app.errors import APIError


@pytest.mark.parametrize("text", ["=SUM(A1)", "  +cmd", "\ufeff@LINK", "-12", "\tvalue", "\nvalue"])
def test_csv_formula_neutralization(text):
    assert csv_cell(text) == "'" + text


def test_untrusted_headers_and_cells_are_escaped():
    snapshot = {
        "kind": "ROW_ERRORS_CSV",
        "columns": ['=HYPERLINK("x")'],
        "rows": [
            {
                "row_number": 4,
                "accepted": False,
                "errors": [],
                "original": {'=HYPERLINK("x")': " \ufeff@SUM(1)"},
            }
        ],
    }
    rows = list(csv.reader(io.StringIO(csv_bytes(snapshot).decode("utf-8-sig"))))
    assert rows[0][-1].startswith("'=") and rows[1][-1].startswith("' ")


def test_exact_balances_sum_all_purposes_and_reject_overdraw():
    items = [{"document_id": "a", "amount": "0.10"}, {"document_id": "a", "amount": "0.20"}]
    assert allocations_within_balances(items, {"a": 30}) == 30
    with pytest.raises(APIError):
        allocations_within_balances(items, {"a": 29})
    with pytest.raises(APIError):
        allocations_within_balances(items, {"b": 30})


@pytest.mark.parametrize(
    "kind,facts",
    [
        ("MSME_REVIEW", {"supplier_classification": "UNKNOWN"}),
        ("RULE37_REVIEW", {"original_claim_period": "2024-01"}),
        ("RULE37A_REVIEW", {"supplier_return_status": "UNKNOWN"}),
        ("IRN_REVIEW", {"irn": "a" * 64, "applicability": "APPLIES"}),
        ("NOTICE_REVIEW", {"notice_reference": "Recorded notice"}),
    ],
)
def test_each_case_kind_keeps_uncertainty_and_requires_evidence(kind, facts):
    assert missing_facts(kind, validate_facts(kind, facts), set())
    with pytest.raises(APIError):
        validate_facts(kind, facts | {"officially_verified": True})


@pytest.mark.parametrize(
    "facts",
    [
        {"amount_paid": "-1"},
        {"amount_paid": 1.0},
        {"amount_paid": "1.001"},
        {"amount_paid": "1e3"},
        {"amount_paid": "NaN"},
        {"original_claim_period": "2024-13"},
        {"amount_paid": "100.01"},
    ],
)
def test_invalid_payment_facts(facts):
    with pytest.raises(APIError):
        validate_facts("RULE37_REVIEW", facts, 10000)


def test_reversal_cannot_exceed_recorded_claim():
    with pytest.raises(APIError):
        validate_facts("RULE37A_REVIEW", {"original_claim_amount": "10", "reversal_amount": "11"})


def test_pdf_markup_rupee_page_and_size_bounds(tmp_path):
    snapshot = {
        "kind": "EVIDENCE_PDF",
        "source_version": 1,
        "provenance": "SYNTHETIC_DEMO",
        "case": {
            "note": "<b>not markup</b> & ₹1180.00",
            "missing": None,
            "long_note": "Readable bounded source text. " * 150,
        },
    }
    content = generate(snapshot, 5242880, 100)
    (tmp_path / "sample-evidence.pdf").write_bytes(content)
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "<b>not markup</b> & ₹1180.00" in text and "UNKNOWN / not recorded" in text
    assert 2 <= len(reader.pages) <= 10
    assert not any("/Annots" in page for page in reader.pages)
    with pytest.raises(ReportFailure, match="REPORT_PAGE_LIMIT") as failure:
        generate(snapshot, 5242880, 1)
    assert failure.value.code == "REPORT_PAGE_LIMIT"
    with pytest.raises(ReportFailure, match="ARTIFACT_SIZE_LIMIT"):
        generate(snapshot, 100, 100)
    with pytest.raises(ReportFailure, match="REPORT_UNSUPPORTED_TEXT"):
        generate(snapshot | {"case": {"note": "unsupported 😀"}}, 5242880, 100)


def test_two_hundred_row_pdf_is_complete_bounded_and_readable(tmp_path):
    from tests.unit.test_import_parsers import ROW

    snapshot = {
        "kind": "RECONCILIATION_PDF",
        "source_version": 2,
        "provenance": "SYNTHETIC_DEMO",
        "total_rows": 2000,
        "manifest": {"generator": "gstshield-reports-v1"},
        "run": {
            "summary": {
                "accepted_purchase_rows": 2000,
                "counts": {"EXACT_MATCH": 2000},
                "tax_exposure_review": "0.00",
            }
        },
        "results": [
            {
                "canonical": ROW | {"invoice_number": f"INV-{index:04d}"},
                "status": "EXACT_MATCH",
                "source_row_number": index,
                "purchase_document_id": "synthetic-document-" + str(index),
                "version": 1,
                "assigned_portal_document_id": "synthetic-portal-" + str(index),
                "reason_codes": [],
                "review_timeline": [],
                "candidates": [],
            }
            for index in range(1, 201)
        ],
    }
    content = generate(snapshot, 5242880, 100)
    (tmp_path / "sample-200-rows.pdf").write_bytes(content)
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Showing 200 of 2000" in text
    assert "INV-0001" in text and "INV-0200" in text
    assert 1 < len(reader.pages) <= 100
    print(f"REPORT_BASELINE rows=200 pages={len(reader.pages)} bytes={len(content)}")


def test_pdf_prints_action_context_and_user_events_once_without_dumping_raw_snapshots(tmp_path):
    from tests.unit.test_import_parsers import ROW

    retained = {
        "invoice": ROW | {"invoice_number": "TRACKED-ONLY-IN-ACTION"},
        "status": "MISSING_IN_SNAPSHOT",
        "recorded_tax": "180.00",
        "reason_codes": ["NO_ELIGIBLE_SNAPSHOT_ROW"],
        "private_diagnostic": "RAW-SNAPSHOT-SENTINEL " * 3000,
    }
    timeline = [
        {
            "kind": "DETECTED",
            "reason": "Initial review needed.",
            "snapshot": retained,
            "created_at": 1713000000,
            "actor_kind": "SYSTEM",
        },
        {
            "kind": "EVIDENCE_CHANGED",
            "reason": "Supplier corrected recorded evidence.",
            "snapshot": {"previous": retained, "current": retained | {"status": "EXACT_MATCH"}},
            "created_at": 1713000001,
            "actor_kind": "SYSTEM",
        },
        {
            "kind": "FOLLOWUP_ATTEMPT",
            "reason": "Supplier contact observed.",
            "snapshot": {"request": "UNIQUE-HUMAN-FOLLOWUP", "delivery": "NOT_VERIFIED"},
            "created_at": 1713000002,
            "actor_kind": "USER",
        },
    ]
    timeline.extend(
        [
            {
                "kind": "SOURCE_REFRESHED",
                "reason": "ROUTINE-REFRESH-REASON",
                "snapshot": {"previous": retained, "current": retained | {"status": "EXACT_MATCH"}},
                "created_at": 1713000003 + index,
                "actor_kind": "SYSTEM",
            }
            for index in range(30)
        ]
    )
    snapshot = {
        "kind": "RECONCILIATION_PDF",
        "source_version": 3,
        "provenance": "SYNTHETIC_DEMO",
        "total_rows": 0,
        "manifest": {"generator": "gstshield-reports-v2"},
        "run": {"summary": {"accepted_purchase_rows": 0}},
        "results": [],
        "action_coverage": {"shown": 1, "total": 1},
        "automation_coverage": {"pending_sources": 0, "error_code": None},
        "business_actions": [
            {
                "id": "synthetic-action",
                "kind": "INVOICE_REVIEW",
                "state": "REVIEW_REQUIRED",
                "version": 3,
                "due_at": None,
                "assigned_to": None,
                "outcome": None,
                "sources_current": True,
                "timeline": timeline,
            }
        ],
    }
    # Legacy retained snapshots have no top-level concise invoice summary.
    content = generate(snapshot, 5242880, 100)
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "TRACKED-ONLY-IN-ACTION" in text
    assert "27PQRSX5678L1Z2" in text and "Recorded GST: 180.00" in text
    assert "MISSING_IN_SNAPSHOT -> EXACT_MATCH" in text
    assert text.count("UNIQUE-HUMAN-FOLLOWUP") == 1
    assert "Source/version refreshes: 30" in text
    assert "first: 2024-04-13T09:20:03+00:00" in text
    assert "last: 2024-04-13T09:20:32+00:00" in text
    assert "ROUTINE-REFRESH-REASON" not in text
    assert "RAW-SNAPSHOT-SENTINEL" not in text
    assert "Full audit snapshots remain in the private application." in text
    assert len(reader.pages) <= 3
    (tmp_path / "sample-actions.pdf").write_bytes(content)
    # New snapshots use the concise current summary, including later invoice context.
    snapshot["business_actions"][0].update(
        {
            "invoice": ROW | {"invoice_number": "LATEST-CONCISE-INVOICE"},
            "comparison_status": "REVIEW_ACCEPTED",
            "recorded_tax": "180.00",
            "reason_codes": [],
        }
    )
    text = "\n".join(
        page.extract_text()
        for page in PdfReader(io.BytesIO(generate(snapshot, 5242880, 100))).pages
    )
    assert "LATEST-CONCISE-INVOICE" in text and "Comparison: REVIEW_ACCEPTED" in text
