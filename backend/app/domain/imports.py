"""Exact canonical import validation, independent of HTTP or storage."""

import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

GSTIN = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
MONEY_FIELDS = (
    "taxable_value",
    "igst",
    "cgst",
    "sgst",
    "cess",
    "other_charges",
    "round_off",
    "gross_total",
)
COMPONENTS = {"igst", "cgst", "sgst", "cess"}
FIELDS = {
    "voucher_id",
    "recipient_gstin",
    "supplier_gstin",
    "invoice_number",
    "invoice_date",
    "document_type",
    *MONEY_FIELDS,
    "supplier_name",
    "irn",
    "total_tax",
    "period",
}
REQUIRED = {
    "supplier_gstin",
    "invoice_number",
    "invoice_date",
    "document_type",
    "taxable_value",
    "other_charges",
    "round_off",
    "gross_total",
}
MAX_MONEY_PAISE = 9999999999999999


class ParseFailure(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def money_paise(value: object, field: str) -> int | None:
    if value is None or value == "":
        if field in COMPONENTS:
            return None
        raise ValueError("MISSING_VALUE")
    if not isinstance(value, str) or not re.fullmatch(r"[+-]?[0-9]{1,14}(\.[0-9]{1,2})?", value):
        raise ValueError("INVALID_MONEY")
    amount = int(Decimal(value) * 100)
    if abs(amount) > MAX_MONEY_PAISE or (amount < 0 and field != "round_off"):
        raise ValueError("INVALID_MONEY")
    return amount


def money_string(paise: int | None) -> str | None:
    if paise is None:
        return None
    return format(Decimal(paise) / 100, ".2f")


def canonical_row(raw: dict, mapping: dict, recipient: str, kind: str, row_number: int) -> dict:
    values = {field: raw.get(header) for field, header in mapping.items()}
    errors = []
    canonical = {}
    amounts = {}

    def invalid(field: str, reason: str) -> None:
        errors.append({"field": field, "reason": reason})

    required = REQUIRED | ({"voucher_id", "recipient_gstin"} if kind == "PURCHASE" else set())
    for field in required:
        value = values.get(field)
        if value is None or value == "" or (isinstance(value, str) and not value.strip()):
            invalid(field, "MISSING_VALUE")
    for field in ("voucher_id", "invoice_number", "supplier_name", "irn"):
        value = values.get(field)
        if value is not None:
            if (
                not isinstance(value, str)
                or len(value) > (1000 if field == "supplier_name" else 128)
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
            ):
                invalid(field, "INVALID_TEXT")
            else:
                canonical[field] = value.strip()
    for field in ("recipient_gstin", "supplier_gstin"):
        value = values.get(field)
        if field == "recipient_gstin" and kind == "PORTAL_2B" and value is None:
            value = recipient
        if not isinstance(value, str) or GSTIN.fullmatch(value) is None:
            invalid(field, "GSTIN_FORMAT_INVALID")
        elif field == "recipient_gstin" and value != recipient:
            invalid(field, "CONTEXT_MISMATCH")
        else:
            canonical[field] = value
    value = values.get("invoice_date")
    if isinstance(value, (date, datetime)):
        value = value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    try:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        canonical["invoice_date"] = date.fromisoformat(value).isoformat()
    except ValueError:
        invalid("invoice_date", "INVALID_DATE")
    document_type = values.get("document_type")
    if document_type not in {"INVOICE", "DEBIT_NOTE", "CREDIT_NOTE"}:
        invalid("document_type", "INVALID_DOCUMENT_TYPE")
    else:
        canonical["document_type"] = document_type
    for field in MONEY_FIELDS:
        try:
            amounts[field] = money_paise(values.get(field), field)
            canonical[field] = money_string(amounts[field])
        except ValueError as exc:
            invalid(field, str(exc))  # Only fixed server-authored reason codes.
    if all(amounts.get(field) is not None for field in COMPONENTS):
        amounts["total_tax"] = sum(amounts[field] for field in COMPONENTS)
    else:
        amounts["total_tax"] = None
    if "total_tax" in values and values["total_tax"] not in (None, ""):
        try:
            reported = money_paise(values["total_tax"], "total_tax")
            if amounts["total_tax"] is not None and reported != amounts["total_tax"]:
                invalid("total_tax", "TAX_TOTAL_INVALID")
        except ValueError:
            invalid("total_tax", "INVALID_MONEY")
    canonical["total_tax"] = money_string(amounts["total_tax"])
    canonical["reason_codes"] = ["COMPONENTS_UNKNOWN"] if amounts["total_tax"] is None else []
    if all(amounts.get(field) is not None for field in MONEY_FIELDS):
        expected = (
            amounts["taxable_value"]
            + amounts["total_tax"]
            + amounts["other_charges"]
            + amounts["round_off"]
        )
        if expected != amounts["gross_total"]:
            invalid("gross_total", "GROSS_TOTAL_INVALID")
    return {
        "row_number": row_number,
        "original": raw,
        "canonical": canonical,
        "amounts": amounts,
        "errors": errors,
        "accepted": not errors,
        "duplicate": False,
    }


def flag_duplicates(rows: list[dict], kind: str) -> int:
    groups = defaultdict(list)
    for row in rows:
        value = row["canonical"]
        identity = tuple(
            value.get(field)
            for field in ("recipient_gstin", "supplier_gstin", "invoice_date", "document_type")
        )
        number = value.get("invoice_number", "").strip().upper()
        if all(identity) and number:
            groups[("identity", *identity, number)].append(row)
        if kind == "PURCHASE" and value.get("voucher_id"):
            groups[("voucher", value["voucher_id"])].append(row)
    for group in groups.values():
        if len(group) > 1:
            for row in group:
                row["duplicate"] = True
                if kind == "PURCHASE" and not any(
                    e["reason"] == "DUPLICATE_IDENTITY" for e in row["errors"]
                ):
                    row["accepted"] = False
                    row["errors"].append(
                        {"field": "invoice_number", "reason": "DUPLICATE_IDENTITY"}
                    )
    return sum(row["duplicate"] for row in rows)
