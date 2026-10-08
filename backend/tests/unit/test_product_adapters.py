import json

import pytest

from app.adapters.imports import parse_import
from app.domain.imports import ParseFailure
from tests.unit.test_import_parsers import RECIPIENT, descriptor, limits


def test_five_column_tax_is_known_but_components_stay_unknown():
    data = (
        b"GSTIN,invoice number,date,taxable value,tax\n27PQRSX5678L1Z2,I"
        b"NV-001,2024-05-10,100000.00,18000.00\n"
    )
    row = parse_import(data, descriptor("five-column-v1"), limits())["rows"][0]
    assert row["accepted"] and row["canonical"]["total_tax"] == "18000.00"
    assert row["canonical"]["igst"] is None and row["canonical"]["cgst"] is None
    assert row["canonical"]["reason_codes"] == ["COMPONENTS_UNKNOWN"]
    assert row["canonical"]["gross_total"] == "118000.00"


def payload():
    return {
        "data": {
            "gstin": RECIPIENT,
            "rtnprd": "052024",
            "docdata": {
                "b2b": [
                    {
                        "ctin": "27PQRSX5678L1Z2",
                        "inv": [
                            {
                                "inum": "INV-001",
                                "idt": "10-05-2024",
                                "val": 118000,
                                "txval": 100000,
                                "igst": 0,
                                "cgst": 9000,
                                "sgst": 9000,
                                "cess": 0,
                                "itcavl": "Y",
                            }
                        ],
                    }
                ]
            },
        }
    }


def test_gst_json_keeps_context_and_actual_components():
    data = payload()
    row = parse_import(
        json.dumps(data).encode(), descriptor("gst-2b-json-v1", kind="PORTAL_2B"), limits()
    )["rows"][0]
    assert row["accepted"] and row["canonical"]["invoice_date"] == "2024-05-10"
    assert row["canonical"]["total_tax"] == "18000.00"
    data["data"]["gstin"] = "29ABCDE1234F1Z5"
    with pytest.raises(ParseFailure, match="CONTEXT_MISMATCH"):
        parse_import(
            json.dumps(data).encode(), descriptor("gst-2b-json-v1", kind="PORTAL_2B"), limits()
        )


def test_gst_json_does_not_drop_unknown_categories_or_availability():
    data = payload()
    data["data"]["docdata"]["b2ba"] = [{"unexpected": "amendment"}]
    with pytest.raises(ParseFailure, match="GST_JSON_CATEGORY_UNSUPPORTED"):
        parse_import(
            json.dumps(data).encode(), descriptor("gst-2b-json-v1", kind="PORTAL_2B"), limits()
        )
    data = payload()
    data["data"]["docdata"]["b2b"][0]["inv"][0]["itcavl"] = "N"
    row = parse_import(
        json.dumps(data).encode(), descriptor("gst-2b-json-v1", kind="PORTAL_2B"), limits()
    )["rows"][0]
    assert not row["accepted"] and row["errors"][0]["reason"] == "PORTAL_ITC_AVAILABILITY_REVIEW"


def test_gst_json_money_decimals_are_not_rounded_through_float():
    data = (
        json.dumps(payload())
        .replace('"val": 118000', '"val": 118000.01')
        .replace('"txval": 100000', '"txval": 100000.01')
    )
    row = parse_import(data.encode(), descriptor("gst-2b-json-v1", kind="PORTAL_2B"), limits())[
        "rows"
    ][0]
    assert row["accepted"] and row["canonical"]["taxable_value"] == "100000.01"


def test_five_column_header_case_and_unknown_tax_split():
    data = (
        b"gstin,INVOICE NUMBER,DATE,TAXABLE VALUE,TAX\n27PQRSX5678L1Z2,I"
        b"NV-001,2024-05-10,100000.00,18000.00\n"
    )
    row = parse_import(data, descriptor("five-column-v1"), limits())["rows"][0]
    assert row["accepted"] and row["canonical"]["igst"] is None
