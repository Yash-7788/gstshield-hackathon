"""Exact item checks. Missing details never establish an item match."""

import unicodedata
from collections import defaultdict
from decimal import Decimal

from app.domain.imports import money_paise, money_string


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").strip().casefold().split())


def grouped(items, use_sku):
    result = defaultdict(
        lambda: {
            "quantity": Decimal(0),
            "value": 0,
            "value_known": True,
            "units": set(),
            "name": "",
        }
    )
    for item in items:
        key = normalized(item["sku"] if use_sku else item["description"])
        row = result[key]
        row["quantity"] += Decimal(item["quantity"])
        value = (
            money_paise(item["taxable_value"], "taxable_value")
            if item.get("taxable_value") is not None
            else None
        )
        row["value_known"] &= value is not None
        if value is not None:
            row["value"] += value
        row["units"].add(normalized(item.get("unit", "")))
        row["name"] = item["description"]
    return result


def compare_items(invoice, evidence):
    receipt_quantity_only = (
        evidence.get("kind") == "RECEIPT" and evidence.get("taxable_value") is None
    )
    header_match = receipt_quantity_only or (
        evidence.get("taxable_value") is not None
        and Decimal(invoice["taxable_value"]) == Decimal(evidence["taxable_value"])
    )
    if invoice.get("quantity") and evidence.get("quantity"):
        header_match &= Decimal(invoice["quantity"]) == Decimal(evidence["quantity"])
    left, right = invoice.get("items", []), evidence.get("items", [])
    if not left or not right:
        return {
            "status": "REVIEW" if header_match else "MISMATCH",
            "lines": [],
            "reason": "Add item details to both records."
            if header_match
            else "Recorded totals differ.",
        }
    use_sku = all(item.get("sku", "").strip() for item in left + right)
    left, right = grouped(left, use_sku), grouped(right, use_sku)
    lines = []
    for key in sorted(left.keys() | right.keys()):
        inv, other = left.get(key), right.get(key)
        equal = bool(
            inv
            and other
            and inv["quantity"] == other["quantity"]
            and (
                receipt_quantity_only
                and not other["value_known"]
                or inv["value_known"]
                and other["value_known"]
                and inv["value"] == other["value"]
            )
        )
        units = (inv["units"] | other["units"]) - {""} if inv and other else set()
        unit_unknown = bool(inv and other and ("" in inv["units"] or "" in other["units"]))
        status = (
            "MISMATCH" if not equal or len(units) > 1 else "REVIEW" if unit_unknown else "MATCHED"
        )
        lines.append(
            {
                "item": (inv or other)["name"],
                "status": status,
                "invoice_quantity": str(inv["quantity"]) if inv else None,
                "record_quantity": str(other["quantity"]) if other else None,
                "invoice_value": money_string(inv["value"]) if inv else None,
                "record_value": money_string(other["value"])
                if other and other["value_known"]
                else None,
            }
        )
    status = (
        "MISMATCH"
        if not header_match or any(row["status"] == "MISMATCH" for row in lines)
        else "REVIEW"
        if any(row["status"] == "REVIEW" for row in lines)
        else "MATCHED"
    )
    return {"status": status, "lines": lines, "reason": "Product, quantity, value and unit checks."}
