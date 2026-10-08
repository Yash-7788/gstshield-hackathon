"""Explainable historical review signals; these do not establish fraud or eligibility."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from statistics import median

from app.domain.imports import money_paise, money_string


def vendor_intelligence(views):
    vendors, signals, groups, banks = {}, [], defaultdict(list), defaultdict(set)
    seen = set()
    for view in views:
        if not view["confirmed"]:
            continue
        fields = view["fields"]
        gstin = fields["supplier_gstin"]
        identity = (gstin, fields["invoice_number"].strip().upper(), fields["invoice_date"])
        if view["findings"]["duplicate_count"]:
            signals.append(
                signal(
                    view,
                    "DUPLICATE",
                    "Another saved invoice has the same supplier, number and date.",
                )
            )
        if identity in seen:
            continue
        seen.add(identity)
        groups[gstin].append(view)
        bank = fields.get("supplier_bank_account")
        if bank:
            banks[bank.upper()].add(gstin)
    for gstin, invoices in groups.items():
        matched = sum(v["findings"]["gst"] == "MATCHED" for v in invoices)
        issues = sum(v["findings"]["summary"] != "MATCHED" for v in invoices)
        missing_irn = disputes = duplicates = 0
        exposure, previous_exposure, correction_seconds = 0, 0, []
        unknown_tax = 0
        totals = [money_paise(v["fields"]["gross_total"], "gross_total") for v in invoices]
        rates = []
        for v in invoices:
            fields, finding = v["fields"], v["findings"]
            base = money_paise(fields["taxable_value"], "taxable_value")
            tax = money_paise(fields.get("total_tax"), "igst")
            if base and tax is not None:
                rates.append(Decimal(tax) / Decimal(base))
            if finding["gst"] != "MATCHED":
                if tax is None:
                    unknown_tax += 1
                else:
                    exposure += tax
            duplicates += bool(finding["duplicate_count"] or finding["gst"] == "DUPLICATE")
            disputes += fields.get("payment_dispute") is True
            irn = fields.get("irn", "")
            if fields.get("irn_required") is True and not irn:
                missing_irn += 1
                signals.append(
                    signal(
                        v,
                        "MISSING_IRN",
                        "Reviewer recorded that an e-invoice reference is required; it is missing.",
                    )
                )
            elif irn and (len(irn) != 64 or any(c not in "0123456789abcdefABCDEF" for c in irn)):
                signals.append(
                    signal(
                        v,
                        "IRN_FORMAT",
                        "Reference format needs review; authenticity is unverified.",
                    )
                )
            if finding["summary"] == "MISMATCH":
                signals.append(
                    signal(
                        v,
                        "RECORD_MISMATCH",
                        "Saved order, receipt or GST evidence differs from the invoice.",
                    )
                )
            bank = fields.get("supplier_bank_account")
            if bank and len(banks[bank.upper()]) > 1:
                signals.append(
                    signal(
                        v,
                        "SHARED_BANK_ACCOUNT",
                        "Different saved suppliers use the same recorded bank account.",
                        related_vendors=sorted(banks[bank.upper()]),
                    )
                )
            if date.fromisoformat(fields["invoice_date"]) > date.today():
                signals.append(
                    signal(v, "FUTURE_INVOICE_DATE", "Invoice date is later than today.")
                )
            start, observed_risk = None, False
            for event in v["history"]:
                if event["action"] != "SOURCE_RECHECKED":
                    continue
                state = event["facts"].get("findings", {}).get("gst")
                if state in {"MISSING", "MISMATCH", "DUPLICATE"}:
                    observed_risk = True
                    if start is None:
                        start = event["at"]
                elif state == "MATCHED" and start is not None:
                    correction_seconds.append(max(0, event["at"] - start))
                    start = None
            if observed_risk and tax is not None:
                previous_exposure += tax
        count = len(invoices)
        amounts = Counter(totals)
        typical = median(totals) if count >= 5 else None
        typical_rate = median(rates) if len(rates) >= 5 else None
        for v, total in zip(invoices, totals, strict=True):
            if amounts[total] >= 3:
                signals.append(
                    signal(
                        v,
                        "REPEATED_AMOUNT",
                        (
                            "At least three distinct invoices from this supplier have the "
                            "same gross amount."
                        ),
                    )
                )
            if typical and total > typical * 3:
                signals.append(
                    signal(
                        v,
                        "AMOUNT_OUTLIER",
                        (
                            "Amount exceeds three times this supplier's observed median; "
                            "review the commercial context."
                        ),
                    )
                )
            base = money_paise(v["fields"]["taxable_value"], "taxable_value")
            tax = money_paise(v["fields"].get("total_tax"), "igst")
            if (
                typical_rate is not None
                and base
                and tax is not None
                and abs(Decimal(tax) / Decimal(base) - typical_rate) > Decimal("0.05")
            ):
                signals.append(
                    signal(
                        v,
                        "TAX_RATE_PATTERN",
                        (
                            "Recorded tax ratio differs by more than five percentage "
                            "points from this supplier's history; verify classification."
                        ),
                    )
                )
        factors = [
            ("GST record match", 40, matched, count),
            (
                "Order item match",
                20,
                sum(v["findings"]["po"] == "MATCHED" for v in invoices),
                count,
            ),
            (
                "Receipt item match",
                20,
                sum(v["findings"]["receipt"] == "MATCHED" for v in invoices),
                count,
            ),
            ("Duplicate check", 20, count - duplicates, count),
        ]
        points = sum(weight * passed // observed for _, weight, passed, observed in factors)
        penalty = min(15, 5 * missing_irn) + min(15, 5 * disputes)
        if correction_seconds and median(correction_seconds) > 7 * 86400:
            penalty += 10
        vendors[gstin] = {
            "gstin": gstin,
            "name": invoices[0]["fields"].get("supplier_name", ""),
            "invoices": count,
            "aligned": matched,
            "issues": issues,
            "score": max(0, points - penalty),
            "basis": (
                "Saved GST, item matches, duplicates, required references, "
                "recorded disputes and observed correction time."
            ),
            "factors": [
                {"name": name, "weight": weight, "passed": passed, "observed": observed}
                for name, weight, passed, observed in factors
            ],
            "recorded_tax_under_review": money_string(exposure) if not unknown_tax else None,
            "known_tax_under_review": money_string(exposure),
            "unknown_tax_invoices": unknown_tax,
            "previous_observed_tax_exposure": money_string(previous_exposure),
            "corrections_observed": len(correction_seconds),
            "median_correction_days": float(Decimal(str(median(correction_seconds))) / 86400)
            if correction_seconds
            else None,
            "missing_required_irns": missing_irn,
            "recorded_disputes": disputes,
            "confidence": "LIMITED_HISTORY" if count < 5 else "OBSERVED_HISTORY",
            "unknowns": (["Tax amount on invoices needing review"] if unknown_tax else [])
            + [
                label
                for field, label in (
                    ("irn_required", "E-invoice applicability"),
                    ("payment_dispute", "Payment disputes"),
                    ("supplier_bank_account", "Bank details"),
                )
                if any(v["fields"].get(field) is None for v in invoices)
            ],
        }
    return list(vendors.values()), signals


def signal(view, kind, meaning, **extra):
    return {
        "invoice_id": view["id"],
        "invoice_number": view["fields"]["invoice_number"],
        "signal": kind,
        "meaning": meaning + " This is a review signal, not proof of fraud.",
        **extra,
    }
