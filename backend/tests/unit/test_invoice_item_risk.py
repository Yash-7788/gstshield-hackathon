"""Exact item boundaries and observed history signals."""

from app.domain.commercial import compare_items
from app.domain.vendor_intelligence import vendor_intelligence


def test_split_lines_units_and_different_products():
    item = {
        "description": "Pump",
        "sku": "A",
        "unit": "pieces",
        "quantity": "10",
        "taxable_value": "100.00",
    }
    invoice = {"taxable_value": "100.00", "quantity": "10", "items": [item]}
    evidence = invoice | {
        "items": [
            item | {"quantity": "4", "taxable_value": "40.00"},
            item | {"quantity": "6", "taxable_value": "60.00"},
        ]
    }
    assert compare_items(invoice, evidence)["status"] == "MATCHED"
    assert compare_items(invoice, invoice | {"items": [item | {"unit": ""}]})["status"] == "REVIEW"
    assert (
        compare_items(invoice, invoice | {"items": [item | {"unit": "kg"}]})["status"] == "MISMATCH"
    )
    assert (
        compare_items(invoice, invoice | {"items": [item | {"sku": "B"}]})["status"] == "MISMATCH"
    )


def test_vendor_history_anomalies_and_explainability():
    views = []
    for i in range(6):
        views.append(
            {
                "id": str(i),
                "confirmed": True,
                "fields": {
                    "supplier_gstin": "SUPPLIER",
                    "invoice_number": str(i),
                    "invoice_date": "2024-05-10",
                    "gross_total": "1180.00" if i < 5 else "10000.00",
                    "taxable_value": "1000.00",
                    "total_tax": "180.00" if i < 5 else "500.00",
                    "supplier_bank_account": "1234567890",
                },
                "findings": {
                    "duplicate_count": 0,
                    "gst": "MATCHED",
                    "po": "MATCHED",
                    "receipt": "MATCHED",
                    "summary": "MATCHED",
                },
                "history": [
                    {
                        "action": "SOURCE_RECHECKED",
                        "at": 1,
                        "facts": {"findings": {"gst": "MISSING"}},
                    },
                    {
                        "action": "SOURCE_RECHECKED",
                        "at": 86401,
                        "facts": {"findings": {"gst": "MATCHED"}},
                    },
                ],
            }
        )
    views.append(
        views[0] | {"id": "other", "fields": views[0]["fields"] | {"supplier_gstin": "OTHER"}}
    )
    vendors, signals = vendor_intelligence(views)
    kinds = {s["signal"] for s in signals}
    assert {"SHARED_BANK_ACCOUNT", "AMOUNT_OUTLIER", "REPEATED_AMOUNT", "TAX_RATE_PATTERN"} <= kinds
    supplier = next(v for v in vendors if v["gstin"] == "SUPPLIER")
    assert supplier["corrections_observed"] == 6
    assert supplier["median_correction_days"] == 1.0
    assert supplier["previous_observed_tax_exposure"] == "1400.00"
    assert supplier["factors"] and supplier["unknowns"]


def test_ocr_refuses_multiple_invoices_and_excess_items(monkeypatch):
    import json

    import pytest

    from app.adapters import gemini
    from app.config import Settings
    from app.errors import APIError

    monkeypatch.setattr(gemini, "generate", lambda *_: json.dumps({"invoice_count": 2}))
    with pytest.raises(APIError) as exc:
        gemini.extract(Settings(), b"fixture", "application/pdf")
    assert exc.value.code == "MULTIPLE_INVOICES"
    monkeypatch.setattr(gemini, "generate", lambda *_: json.dumps({"items": [{}] * 101}))
    with pytest.raises(APIError) as exc:
        gemini.extract(Settings(), b"fixture", "application/pdf")
    assert exc.value.code == "AI_RESPONSE_INVALID"
