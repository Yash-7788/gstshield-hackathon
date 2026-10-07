"""Deterministic matching policy. Money is integer paise; similarity is not evidence."""

import re
from collections import Counter, defaultdict
from decimal import ROUND_FLOOR, Decimal

from rapidfuzz.fuzz import ratio

from app.domain.imports import MONEY_FIELDS, ParseFailure, money_string

STATUSES = (
    "EXACT_MATCH",
    "FUZZY_SUGGESTION",
    "AMOUNT_MISMATCH",
    "MISSING_IN_SNAPSHOT",
    "AMBIGUOUS",
    "EVIDENCE_INCOMPLETE",
    "REVIEW_ACCEPTED",
    "REJECTED",
)
EXPOSURE = {
    "AMOUNT_MISMATCH",
    "MISSING_IN_SNAPSHOT",
    "AMBIGUOUS",
    "EVIDENCE_INCOMPLETE",
    "REJECTED",
}
IDENTITY_FIELDS = ("recipient_gstin", "supplier_gstin", "document_type", "invoice_date")


def exact_number(value):
    return value.strip().upper()


def comparison_number(value):
    # Only explicit ASCII separators are removed. Digits, leading zeroes and year
    # tokens survive; Unicode characters are not transliterated into new identities.
    return re.sub(r"[ /._-]", "", exact_number(value))


def identity(row):
    return tuple(row["canonical"].get(field) for field in IDENTITY_FIELDS)


def key(row):
    return (*identity(row), exact_number(row["canonical"].get("invoice_number", "")))


def amount_comparison(purchase, portal, tolerance):
    differences = {}
    unknown = False
    for field in MONEY_FIELDS:
        left, right = purchase["amounts"].get(field), portal["amounts"].get(field)
        if left is None or right is None:
            unknown = True
            differences[field] = None
        else:
            differences[field] = money_string(left - right)
    mismatch = any(
        purchase["amounts"].get(field) is not None
        and portal["amounts"].get(field) is not None
        and abs(purchase["amounts"][field] - portal["amounts"][field]) > tolerance
        for field in MONEY_FIELDS
    )
    reasons = []
    if unknown:
        reasons.append("COMPONENTS_UNKNOWN")
    if mismatch:
        reasons.append("TAX_COMPONENT_MISMATCH")
    return not unknown and not mismatch, differences, reasons


def summarize(rows):
    counts = dict.fromkeys(STATUSES, 0)
    exposure = credit = unknown_exposure = unknown_credit = 0
    for row in rows:
        counts[row["status"]] += 1
        if row["status"] not in EXPOSURE:
            continue
        is_credit = row["document_type"] == "CREDIT_NOTE"
        if row["total_tax"] is None:
            if is_credit:
                unknown_credit += 1
            else:
                unknown_exposure += 1
        elif is_credit:
            credit += row["total_tax"]
        else:
            exposure += row["total_tax"]
    return {
        "accepted_purchase_rows": sum(counts.values()),
        "counts": counts,
        "tax_exposure_review": money_string(exposure),
        "credit_note_tax_review": money_string(credit),
        "unknown_tax_exposure_rows": unknown_exposure,
        "unknown_credit_note_tax_rows": unknown_credit,
        "currency": "INR",
    }


def reconcile(purchases, portals, policy):
    """Evaluate the whole candidate graph before assigning suggestions/classifying ties."""
    tolerance = int(Decimal(policy["amount_tolerance"]) * 100)
    threshold = Decimal(policy["fuzzy_threshold"])
    threshold_float = float(threshold)
    gap = Decimal(policy["fuzzy_gap"])
    purchase_counts = Counter(key(row) for row in purchases if all(identity(row)))
    portal_counts = Counter(key(row) for row in portals if all(identity(row)))
    exact = defaultdict(list)
    groups = defaultdict(list)
    same_number = defaultdict(list)
    for portal in portals:
        exact[key(portal)].append(portal)
        same_number[key(portal)[:-1][:-1] + (key(portal)[-1],)].append(portal)
        if portal["accepted"]:
            groups[identity(portal)].append(
                (portal, comparison_number(portal["canonical"]["invoice_number"]))
            )
    results = []
    reserved = set()
    pairs = candidates = 0

    def candidate(purchase, portal, score):
        nonlocal candidates
        candidates += 1
        if candidates > policy["max_candidates"]:
            raise ParseFailure("MATCH_CANDIDATE_LIMIT")
        eligible, differences, reasons = amount_comparison(purchase, portal, tolerance)
        if portal["duplicate"] or portal_counts[key(portal)] > 1:
            eligible = False
            reasons.append("DUPLICATE_IDENTITY")
        if not portal["accepted"]:
            eligible = False
            reasons.append("PORTAL_ROW_REJECTED")
        if portal["row_number"] in reserved:
            eligible = False
            reasons.append("PORTAL_ALREADY_ASSIGNED")
        if purchase["duplicate"] or purchase_counts[key(purchase)] > 1:
            eligible = False
            reasons.append("DUPLICATE_IDENTITY")
        return {
            "portal_row_number": portal["row_number"],
            "score": format(score.quantize(Decimal("0.01"), rounding=ROUND_FLOOR), ".2f"),
            "score_raw": str(score),
            "hard_gates_passed": eligible,
            "amount_differences": differences,
            "original_invoice_number": portal["canonical"]["invoice_number"],
            "invoice_date": portal["canonical"]["invoice_date"],
            "reason_codes": sorted(set(reasons)),
        }

    # Exact classification first: no fuzzy candidate may silently displace an exact identity.
    for purchase in purchases:
        if not purchase["accepted"]:
            continue
        result = {
            "source_row_number": purchase["row_number"],
            "canonical": purchase["canonical"],
            "status": "MISSING_IN_SNAPSHOT",
            "reason_codes": [],
            "candidates": [],
            "assigned_portal_row": None,
        }
        results.append(result)
        matches = exact[key(purchase)]
        result["candidates"] = [candidate(purchase, portal, Decimal(100)) for portal in matches]
        if (
            purchase["duplicate"]
            or purchase_counts[key(purchase)] > 1
            or any("DUPLICATE_IDENTITY" in item["reason_codes"] for item in result["candidates"])
        ):
            result["status"] = "AMBIGUOUS"
            result["reason_codes"] = ["DUPLICATE_IDENTITY"]
        elif any(purchase["amounts"].get(field) is None for field in MONEY_FIELDS):
            result["status"] = "EVIDENCE_INCOMPLETE"
            result["reason_codes"] = ["COMPONENTS_UNKNOWN"]
        elif matches:
            item = result["candidates"][0]
            if item["hard_gates_passed"]:
                result["status"] = "EXACT_MATCH"
                result["assigned_portal_row"] = item["portal_row_number"]
                reserved.add(item["portal_row_number"])
                result["reason_codes"] = ["EXACT_IDENTITY_AND_AMOUNTS"]
                if any(
                    value not in (None, "0.00") for value in item["amount_differences"].values()
                ):
                    result["reason_codes"].append("WITHIN_AMOUNT_TOLERANCE")
            else:
                incomplete = (
                    "COMPONENTS_UNKNOWN" in item["reason_codes"] or not matches[0]["accepted"]
                )
                result["status"] = "EVIDENCE_INCOMPLETE" if incomplete else "AMOUNT_MISMATCH"
                result["reason_codes"] = item["reason_codes"]

    by_position = {row["row_number"]: row for row in purchases}
    edges = defaultdict(set)
    for result in results:
        purchase = by_position[result["source_row_number"]]
        if result["status"] != "MISSING_IN_SNAPSHOT":
            continue
        number = comparison_number(purchase["canonical"]["invoice_number"])
        for portal, other in groups[identity(purchase)]:
            pairs += 1
            if pairs > policy["max_pairs"]:
                raise ParseFailure("MATCH_PAIR_LIMIT")
            if not number or not other:
                continue
            # Floor, never round a score up across the threshold. Financial values
            # never enter RapidFuzz or floating point arithmetic.
            similarity = ratio(number, other)
            # Reject clear negatives cheaply; survivors still pass the exact Decimal
            # floor gate below. Scores never determine money or legal eligibility.
            if similarity < threshold_float:
                continue
            raw_score = Decimal(str(similarity))
            score = raw_score.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
            if score < threshold:
                continue
            item = candidate(purchase, portal, raw_score)
            result["candidates"].append(item)
            if item["hard_gates_passed"]:
                edges[item["portal_row_number"]].add(result["source_row_number"])
        eligible = [item for item in result["candidates"] if item["hard_gates_passed"]]
        eligible.sort(key=lambda item: Decimal(item["score_raw"]), reverse=True)
        if eligible:
            result["status"] = "FUZZY_SUGGESTION"
            result["reason_codes"] = ["HUMAN_REVIEW_REQUIRED"]
            if len(eligible) > 1:
                score_gap = Decimal(eligible[0]["score_raw"]) - Decimal(eligible[1]["score_raw"])
                if score_gap == 0 or score_gap < gap:
                    result["status"] = "AMBIGUOUS"
                    result["reason_codes"] = ["LOW_SCORE_GAP"]
        elif result["candidates"]:
            reasons = sorted(
                {reason for item in result["candidates"] for reason in item["reason_codes"]}
            )
            incomplete = "COMPONENTS_UNKNOWN" in reasons
            ambiguous = "DUPLICATE_IDENTITY" in reasons or "PORTAL_ALREADY_ASSIGNED" in reasons
            result["status"] = (
                "AMBIGUOUS"
                if ambiguous
                else "EVIDENCE_INCOMPLETE"
                if incomplete
                else "AMOUNT_MISMATCH"
            )
            result["reason_codes"] = reasons
        else:
            context_number = key(purchase)[:-1][:-1] + (key(purchase)[-1],)
            if any(
                portal["canonical"].get("invoice_date")
                and portal["canonical"]["invoice_date"][:4]
                != purchase["canonical"]["invoice_date"][:4]
                for portal in same_number[context_number]
            ):
                result["reason_codes"] = ["SAME_NUMBER_DIFFERENT_YEAR"]
            elif any(not portal["accepted"] for portal in same_number[context_number]):
                result["status"] = "EVIDENCE_INCOMPLETE"
                result["reason_codes"] = ["PORTAL_ROW_REJECTED"]
            else:
                result["reason_codes"] = ["NO_ELIGIBLE_SNAPSHOT_ROW"]

    # Any shared eligible portal connects a contested component. Every purchase
    # touching that component is ambiguous, even if its own top score has a gap.
    contested = {
        position for positions in edges.values() if len(positions) > 1 for position in positions
    }
    for result in results:
        if result["source_row_number"] in contested:
            result["status"] = "AMBIGUOUS"
            result["reason_codes"] = sorted(set(result["reason_codes"] + ["MULTIPLE_CANDIDATES"]))
        result["candidates"].sort(
            key=lambda item: (
                -Decimal(item["score"]),
                item["original_invoice_number"],
                item["portal_row_number"],
            )
        )
        for rank, item in enumerate(result["candidates"], 1):
            item["rank"] = rank
            item.pop("score_raw")
    return {"results": results, "compared_pairs": pairs, "candidate_count": candidates}
