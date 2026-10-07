"""Exact parser behavior and hostile input boundaries."""

import csv
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook

from app.adapters.imports import parse_import
from app.config import Settings
from app.domain.imports import ParseFailure, money_paise
from app.jobs.imports import LIMIT_NAMES

RECIPIENT = "27ABCDE1234F1Z5"
ROW = {
    "voucher_id": "V1",
    "recipient_gstin": RECIPIENT,
    "supplier_gstin": "27PQRSX5678L1Z2",
    "invoice_number": "INV-001",
    "invoice_date": "2024-04-10",
    "document_type": "INVOICE",
    "taxable_value": "1000.00",
    "igst": "0.00",
    "cgst": "90.00",
    "sgst": "90.00",
    "cess": "0.00",
    "other_charges": "0.00",
    "round_off": "0.00",
    "gross_total": "1180.00",
}


def csv_content(rows=None, headers=None):
    rows = rows if rows is not None else [ROW]
    headers = headers if headers is not None else list(ROW)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(header, "") for header in headers])
    return stream.getvalue().encode()


def descriptor(adapter="csv-v1", **changes):
    value = {
        "adapter_version": adapter,
        "kind": "PURCHASE",
        "recipient_gstin": RECIPIENT,
        "period": "2024-05",
        "mapping": {},
        "sheet_name": None,
    }
    value.update(changes)
    return value


def limits(**changes):
    settings = Settings()
    return {key: getattr(settings, key) for key in LIMIT_NAMES} | changes


def xlsx_content(rows=None, *, extra_sheet=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Purchases"
    sheet.append(list(ROW))
    for row in [ROW] if rows is None else rows:
        sheet.append([row.get(field) for field in ROW])
    if extra_sheet:
        workbook.create_sheet("Other")
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_exact_money_and_older_invoice():
    result = parse_import(b"\xef\xbb\xbf" + csv_content(), descriptor(), limits())
    row = result["rows"][0]
    assert row["accepted"] and row["amounts"]["gross_total"] == 118000
    assert row["canonical"]["total_tax"] == "180.00"
    assert row["canonical"]["invoice_date"] == "2024-04-10"


@pytest.mark.parametrize(
    "value", [True, 1.01, "1.001", "1e3", "NaN", "Infinity", "-1", " 1.00", "1,000.00", "", None]
)
def test_money_never_rounds(value):
    with pytest.raises(ValueError):
        money_paise(value, "taxable_value")


def test_unknown_components():
    row = parse_import(
        csv_content([{**ROW, "igst": "", "round_off": "-0.01"}]), descriptor(), limits()
    )["rows"][0]
    assert row["accepted"] and row["canonical"]["igst"] is None
    assert row["canonical"]["total_tax"] is None
    assert row["canonical"]["reason_codes"] == ["COMPONENTS_UNKNOWN"]
    assert money_paise("-0.01", "round_off") == -1


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("invoice_number", "   ", "MISSING_VALUE"),
        ("invoice_date", "2024-02-30", "INVALID_DATE"),
        ("recipient_gstin", "29ABCDE1234F1Z5", "CONTEXT_MISMATCH"),
        ("supplier_gstin", "invalid", "GSTIN_FORMAT_INVALID"),
        ("document_type", "OTHER", "INVALID_DOCUMENT_TYPE"),
        ("gross_total", "1180.01", "GROSS_TOTAL_INVALID"),
    ],
)
def test_rejected_rows(field, value, reason):
    row = parse_import(csv_content([{**ROW, field: value}]), descriptor(), limits())["rows"][0]
    assert not row["accepted"] and row["original"][field] == value
    assert reason in {error["reason"] for error in row["errors"]}


def test_duplicates():
    result = parse_import(csv_content([ROW, ROW]), descriptor(), limits())
    assert result["duplicate_rows"] == 2 and all(not row["accepted"] for row in result["rows"])
    result = parse_import(csv_content([ROW, ROW]), descriptor(kind="PORTAL_2B"), limits())
    assert result["duplicate_rows"] == 2 and all(row["accepted"] for row in result["rows"])


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", "UPLOAD_SIZE_INVALID"),
        (b"a,a\n1,2", "DUPLICATE_HEADERS"),
        (b"a,b\n1", "CSV_ROW_WIDTH_INVALID"),
        (b"a\n\xff", "UTF8_REQUIRED"),
        (b"a\n\x00", "INVALID_CSV"),
        (b'a\n"unclosed', "INVALID_CSV"),
    ],
)
def test_malformed_csv(content, code):
    with pytest.raises(ParseFailure, match=code):
        parse_import(content, descriptor(), limits())


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"max_import_rows": 1}, "ROW_LIMIT"),
        ({"max_import_columns": 2}, "COLUMN_LIMIT"),
        ({"max_cell_characters": 3}, "INVALID_CSV"),
        ({"max_parsed_import_bytes": 20}, "PARSED_RESULT_LIMIT"),
    ],
)
def test_resource_bounds(change, code):
    with pytest.raises(ParseFailure, match=code):
        parse_import(
            csv_content([ROW, {**ROW, "voucher_id": "V2", "invoice_number": "I2"}]),
            descriptor(),
            limits(**change),
        )


def test_custom_mapping():
    renamed = {"Voucher": "V1", **{key: value for key, value in ROW.items() if key != "voucher_id"}}
    content = csv_content([renamed], list(renamed))
    result = parse_import(content, descriptor(), limits())
    assert result["errors"] == [{"field": "voucher_id", "reason": "MAPPING_REQUIRED"}]
    mapping = {key: key for key in ROW if key != "voucher_id"} | {"voucher_id": "Voucher"}
    assert parse_import(content, descriptor(mapping=mapping), limits())["rows"][0]["accepted"]


def test_xlsx_numeric_and_sheet_selection():
    row = {**ROW, "taxable_value": 1000, "gross_total": 1180, "cgst": 90, "sgst": 90}
    assert parse_import(xlsx_content([row]), descriptor("xlsx-v1"), limits())["rows"][0]["accepted"]
    content = xlsx_content(extra_sheet=True)
    with pytest.raises(ParseFailure, match="SHEET_SELECTION_REQUIRED"):
        parse_import(content, descriptor("xlsx-v1"), limits())
    assert parse_import(content, descriptor("xlsx-v1", sheet_name="Purchases"), limits())["rows"][
        0
    ]["accepted"]


def test_xlsx_formula_expansion_and_traversal():
    with pytest.raises(ParseFailure, match="XLSX_FORMULA_UNSUPPORTED"):
        parse_import(
            xlsx_content([{**ROW, "gross_total": "=1000+180"}]), descriptor("xlsx-v1"), limits()
        )
    with pytest.raises(ParseFailure, match="XLSX_EXPANSION_LIMIT"):
        parse_import(xlsx_content(), descriptor("xlsx-v1"), limits(max_xlsx_uncompressed_bytes=100))
    stream = io.BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../evil.xml", "<xml/>")
    with pytest.raises(ParseFailure, match="XLSX_UNSAFE_ARCHIVE"):
        parse_import(stream.getvalue(), descriptor("xlsx-v1"), limits())


def demo_content(**changes):
    value = {
        "format": "canonical-demo-v1",
        "provenance": "SYNTHETIC_DEMO",
        "recipient_gstin": RECIPIENT,
        "period": "2024-05",
        "generated_at": "2024-06-14T00:00:00Z",
        "documents": [
            {
                key: value
                for key, value in ROW.items()
                if key not in {"voucher_id", "recipient_gstin"}
            }
        ],
    }
    return json.dumps(value | changes).encode()


def test_demo_context_and_json_bounds():
    assert parse_import(
        demo_content(), descriptor("canonical-demo-v1", kind="PORTAL_2B"), limits()
    )["rows"][0]["accepted"]
    with pytest.raises(ParseFailure, match="CONTEXT_MISMATCH"):
        parse_import(
            demo_content(period="2024-06"),
            descriptor("canonical-demo-v1", kind="PORTAL_2B"),
            limits(),
        )
    with pytest.raises(ParseFailure, match="JSON_DEPTH_LIMIT"):
        parse_import(b"[" * 25 + b"]" * 25, descriptor("canonical-demo-v1"), limits())
    with pytest.raises(ParseFailure, match="DUPLICATE_JSON_KEY"):
        parse_import(b'{"format":1,"format":2}', descriptor("canonical-demo-v1"), limits())


def test_blank_records_and_reported_tax_keep_validation_truth():
    content = csv_content() + b"\n" + csv_content().split(b"\n", 1)[1]
    result = parse_import(content, descriptor(), limits())
    assert [row["row_number"] for row in result["rows"]] == [1, 2, 3]
    assert not result["rows"][1]["accepted"]
    row = ROW | {"total_tax": "181.00"}
    result = parse_import(csv_content([row], list(row)), descriptor(), limits())
    assert not result["rows"][0]["accepted"]
    assert any(error["reason"] == "TAX_TOTAL_INVALID" for error in result["rows"][0]["errors"])


def test_unsafe_xml_entities_are_rejected_before_openpyxl():
    content = xlsx_content()
    source = ZipFile(io.BytesIO(content))
    stream = io.BytesIO()
    with source, ZipFile(stream, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            raw = source.read(entry)
            if entry.filename == "xl/workbook.xml":
                raw = b'<!DOCTYPE doc [<!ENTITY a "private">]><doc>&a;</doc>'
            target.writestr(entry, raw)
    with pytest.raises(ParseFailure, match="INVALID_XLSX"):
        parse_import(stream.getvalue(), descriptor("xlsx-v1"), limits())


def test_invalid_duplicate_does_not_make_other_copy_acceptable():
    result = parse_import(csv_content([ROW, ROW | {"gross_total": "1.00"}]), descriptor(), limits())
    assert result["duplicate_rows"] == 2
    assert all(not row["accepted"] for row in result["rows"])


def test_repo_examples_parse_with_explicit_provenance():
    from pathlib import Path

    directory = Path(__file__).resolve().parents[2] / "examples"
    result = parse_import((directory / "purchase.csv").read_bytes(), descriptor(), limits())
    assert result["rows"][0]["accepted"]
    result = parse_import(
        (directory / "portal_demo.json").read_bytes(),
        descriptor("canonical-demo-v1", kind="PORTAL_2B"),
        limits(),
    )
    assert result["rows"][0]["accepted"]
