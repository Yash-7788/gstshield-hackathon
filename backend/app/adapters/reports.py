"""Offline PDF and spreadsheet-safe CSV generation from immutable snapshots."""

import csv
import hashlib
import io
from datetime import UTC, datetime
from html import escape
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

FONT = Path(__file__).resolve().parents[1] / "assets" / "NotoSans-Regular.ttf"
FONT_SHA256 = "b85c38ecea8a7cfb39c24e395a4007474fa5a4fc864f6ee33309eb4948d232d5"


class ReportFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def csv_cell(value):
    text = "" if value is None else str(value)
    # Excel may ignore leading whitespace/BOM before evaluating a formula.
    if text.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def csv_bytes(snapshot):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    if snapshot["kind"] == "PROPOSAL_CSV":
        writer.writerow(
            [
                "instruction",
                "provenance",
                "document_id",
                "invoice_number",
                "supplier_gstin",
                "gross_total",
                "amount_paid",
                "remaining_balance",
                "proposed_amount",
                "purpose",
                "payment_observed_on",
                "evidence_case_id",
                "case_version",
            ]
        )
        balances = {item["document_id"]: item for item in snapshot["proposal"]["balances"]}
        for allocation in snapshot["proposal"]["allocations"]:
            balance = balances[allocation["document_id"]]
            writer.writerow(
                [
                    csv_cell(value)
                    for value in (
                        "PROPOSAL_ONLY",
                        snapshot["provenance"],
                        allocation["document_id"],
                        balance["invoice_number"],
                        balance["supplier_gstin"],
                        balance["gross_total"],
                        balance["amount_paid"],
                        balance["remaining_balance"],
                        allocation["amount"],
                        allocation["purpose"],
                        balance["payment_observed_on"],
                        balance["case_id"],
                        balance["case_version"],
                    )
                ]
            )
    else:
        headers = snapshot["columns"]
        writer.writerow(
            ["source_row_number", "accepted", "errors", *[csv_cell(header) for header in headers]]
        )
        for row in snapshot["rows"]:
            writer.writerow(
                [
                    row["row_number"],
                    row["accepted"],
                    csv_cell(str(row["errors"])),
                    *[csv_cell(row["original"].get(header)) for header in headers],
                ]
            )
    return stream.getvalue().encode("utf-8-sig")


def pdf_bytes(snapshot, max_pages):
    if hashlib.sha256(FONT.read_bytes()).hexdigest() != FONT_SHA256:
        raise ReportFailure("REPORT_FONT_INVALID")
    font = TTFont("GSTNoto", str(FONT))
    pdfmetrics.registerFont(font)
    supported = font.face.charToGlyph
    styles = {
        "body": ParagraphStyle(
            "body", fontName="GSTNoto", fontSize=9, leading=13, spaceAfter=4, wordWrap="CJK"
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName="GSTNoto",
            fontSize=12,
            leading=17,
            textColor=colors.HexColor("#12536a"),
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "title": ParagraphStyle(
            "title", fontName="GSTNoto", fontSize=20, leading=25, spaceAfter=10
        ),
    }
    story = []

    def paragraph(value, style="body"):
        text = str(value)
        if any(ord(char) not in supported for char in text if char not in "\n\t\r"):
            raise ReportFailure("REPORT_UNSUPPORTED_TEXT")
        if any(ord(char) < 32 for char in text if char not in "\n\t\r"):
            raise ReportFailure("REPORT_UNSUPPORTED_TEXT")
        # Limit each flowable's height without dropping source text.
        for start in range(0, max(1, len(text)), 400):
            safe = escape(text[start : start + 400]).replace("\n", "<br/>").replace("\t", "    ")
            story.append(Paragraph(safe or " ", styles[style]))

    paragraph("GSTShield — human review report", "title")
    paragraph(snapshot["kind"].replace("_", " "), "heading")
    paragraph(
        "Snapshot of recorded observations. This report does not determine legal ITC "
        "eligibility, verify government records, file returns, or execute payments."
    )
    paragraph("Provenance: " + snapshot["provenance"])
    paragraph(
        "Source version: "
        + str(snapshot["source_version"])
        + ". Later changes are not included; check current application records before acting."
    )
    if "total_rows" in snapshot:
        paragraph(
            f"Showing {len(snapshot['results'])} of {snapshot['total_rows']} result rows. "
            "Summary totals cover the complete run; omitted rows remain in the application."
        )
    story.append(Spacer(1, 4 * mm))

    def walk(value, path="", depth=0):
        if depth > 16:
            raise ReportFailure("REPORT_NESTING_LIMIT")
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, path + " / " + str(key) if path else str(key), depth + 1)
        elif isinstance(value, list):
            if not value:
                paragraph(path + ": []")
            for index, item in enumerate(value, 1):
                if isinstance(item, dict):
                    paragraph(path + " #" + str(index), "heading")
                walk(item, path + " #" + str(index), depth + 1)
        else:
            if path.rsplit(" / ", 1)[-1] in {
                "created_at",
                "updated_at",
                "expires_at",
            } and isinstance(value, int):
                value = datetime.fromtimestamp(value, UTC).isoformat()
            paragraph(path + ": " + ("UNKNOWN / not recorded" if value is None else str(value)))

    if snapshot["kind"] == "RECONCILIATION_PDF":
        walk({"source_manifest": snapshot["manifest"], "run": snapshot["run"]})
        for index, result in enumerate(snapshot["results"], 1):
            start = len(story)
            canonical = result["canonical"]
            paragraph(
                f"Result {index} | source row {result['source_row_number']} | {result['status']}",
                "heading",
            )
            paragraph(
                f"Invoice: {canonical.get('invoice_number')} | "
                f"Date: {canonical.get('invoice_date')} "
                f"| Type: {canonical.get('document_type')}"
            )
            paragraph(
                f"Supplier: {canonical.get('supplier_gstin')} | "
                f"{canonical.get('supplier_name') or 'Name not recorded'}"
            )
            paragraph(
                f"Document: {result['purchase_document_id']} | result version: {result['version']} "
                f"| assigned portal document: {result['assigned_portal_document_id'] or 'NONE'}"
            )
            for fields in (
                ("taxable_value", "gross_total", "total_tax"),
                ("igst", "cgst", "sgst", "cess"),
                ("other_charges", "round_off"),
            ):
                paragraph(
                    " | ".join(
                        name
                        + ": "
                        + (
                            str(canonical.get(name))
                            if canonical.get(name) is not None
                            else "UNKNOWN"
                        )
                        for name in fields
                    )
                )
            paragraph("Reasons: " + ", ".join(result["reason_codes"]))
            if result.get("review_timeline"):
                walk(result["review_timeline"], "Human review history")
            if result.get("candidates"):
                paragraph(
                    f"{len(result['candidates'])} candidate(s) recorded. "
                    "Candidate evidence remains in the application."
                )
            group = story[start:]
            del story[start:]
            story.append(KeepTogether(group))
    else:
        walk(
            {
                key: value
                for key, value in snapshot.items()
                if key
                not in {
                    "kind",
                    "provenance",
                    "source_version",
                    "business_actions",
                    "action_versions",
                    "action_coverage",
                    "automation_coverage",
                }
            }
        )
    if "action_coverage" in snapshot:
        paragraph("Business actions and follow-up history", "heading")
        coverage = snapshot["action_coverage"]
        paragraph(
            f"Showing {coverage['shown']} of {coverage['total']} recorded actions. "
            "Full audit snapshots remain in the private application."
        )
        automation = snapshot.get("automation_coverage", {})
        paragraph(
            f"Pending evidence checks: {automation.get('pending_sources', 'UNKNOWN')}. "
            f"Automation error: {automation.get('error_code') or 'NONE RECORDED'}."
        )
        for action in snapshot.get("business_actions", []):
            paragraph(action["kind"].replace("_", " ") + " | " + action["state"], "heading")
            paragraph(
                f"Action: {action['id']} | version: {action['version']} | "
                f"Current evidence: {action['sources_current']}"
            )
            # Old retained snapshots did not contain this concise source summary.
            source = action
            if "invoice" not in source:
                source = next(
                    (
                        event["snapshot"].get("current", event["snapshot"])
                        for event in reversed(action["timeline"])
                        if event["kind"] in {"DETECTED", "SOURCE_REFRESHED", "EVIDENCE_CHANGED"}
                    ),
                    {},
                )
            invoice = source.get("invoice", {})
            paragraph(
                f"Invoice: {invoice.get('invoice_number', 'NOT RECORDED')} | "
                f"Date: {invoice.get('invoice_date', 'NOT RECORDED')} | "
                f"Type: {invoice.get('document_type', 'NOT RECORDED')}"
            )
            paragraph(
                f"Supplier: {invoice.get('supplier_gstin', 'NOT RECORDED')} | "
                f"Comparison: {source.get('comparison_status', source.get('status', 'UNKNOWN'))} | "
                f"Recorded GST: {source.get('recorded_tax') or 'UNKNOWN'}"
            )
            paragraph("Reasons: " + ", ".join(source.get("reason_codes", [])))
            due = action["due_at"]
            paragraph(
                "Recorded review date: "
                + (datetime.fromtimestamp(due, UTC).date().isoformat() if due else "NOT RECORDED")
            )
            paragraph("Assigned reviewer: " + (action["assigned_to"] or "NOT ASSIGNED"))
            walk(action["outcome"], "Recorded outcome; external execution not verified")
            refreshes = [
                event for event in action["timeline"] if event["kind"] == "SOURCE_REFRESHED"
            ]
            if refreshes:
                first = datetime.fromtimestamp(
                    min(e["created_at"] for e in refreshes), UTC
                ).isoformat()
                last = datetime.fromtimestamp(
                    max(e["created_at"] for e in refreshes), UTC
                ).isoformat()
                paragraph(
                    f"Source/version refreshes: {len(refreshes)} | first: {first} | last: {last}. "
                    "Individual refresh entries remain in the private audit history."
                )
            for event in action["timeline"]:
                if event["kind"] == "SOURCE_REFRESHED":
                    continue
                when = datetime.fromtimestamp(event["created_at"], UTC).isoformat()
                paragraph(f"{when} | {event['kind']} | {event['actor_kind']}")
                paragraph(event["reason"])
                details = event["snapshot"]
                if event["kind"] == "EVIDENCE_CHANGED":
                    previous, current = details["previous"], details["current"]
                    paragraph(
                        f"Comparison: {previous['status']} -> {current['status']}; "
                        f"recorded GST: {current['recorded_tax'] or 'UNKNOWN'}. "
                        "Renewed review required; this is not a filed return."
                    )
                elif event["kind"] in {"FOLLOWUP_DRAFT", "FOLLOWUP_ATTEMPT"}:
                    walk(
                        {
                            k: details[k]
                            for k in ("contact", "request", "delivery", "observed_on")
                            if k in details
                        },
                        "Follow-up",
                    )
                elif event["kind"] in {
                    "FILING_OBSERVATION",
                    "NOTICE_SUBMISSION_OBSERVATION",
                    "REVIEW_DECISION",
                }:
                    walk(details, "Dated user observation")
                elif event["kind"] == "REVIEW_DUE":
                    paragraph("Recorded review date reached. No message has been sent.")
        paragraph(
            "Review candidates and recorded outcomes do not guarantee legal eligibility, "
            "government submission, payment execution or tax recovery."
        )
    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=(210 * mm, 297 * mm),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="GSTShield review snapshot",
        author="GSTShield local demo",
    )

    def page(canvas, doc):
        if doc.page > max_pages:
            raise ReportFailure("REPORT_PAGE_LIMIT")
        canvas.saveState()
        canvas.setFont("GSTNoto", 8)
        canvas.drawString(18 * mm, 10 * mm, "Human review only | " + snapshot["provenance"])
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    try:
        document.build(story, onFirstPage=page, onLaterPages=page)
    except ReportFailure as exc:
        # ReportLab annotates callback exceptions by reconstructing their type.
        # Keep the stable public code instead of exposing its internal annotation.
        if exc.code.endswith("REPORT_PAGE_LIMIT"):
            raise ReportFailure("REPORT_PAGE_LIMIT") from None
        raise
    return stream.getvalue()


def generate(snapshot, max_bytes, max_pages):
    content = (
        pdf_bytes(snapshot, max_pages) if snapshot["kind"].endswith("_PDF") else csv_bytes(snapshot)
    )
    if len(content) > max_bytes:
        raise ReportFailure("ARTIFACT_SIZE_LIMIT")
    return content


def generator_manifest():
    return {
        "generator": "gstshield-reports-v2",
        "reportlab": reportlab.Version,
        "font": "NotoSans-Regular",
        "font_sha256": FONT_SHA256,
        "verification": "USER_OBSERVATIONS_ONLY",
    }
