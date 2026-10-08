"""Explicit access inventory for the invoice, knowledge, product and channel routes."""

from tests.integration.test_passports import FIELDS


def inventory(rid, identifier):
    scope = {"registration_id": rid, "period": "2024-05"}
    version = {"expected_version": 1}
    signature = "a" * 64
    query_reads = {
        "/passports",
        "/product/business",
        "/product/owner-summary",
        "/product/contributions",
        "/product/schemes",
        "/product/workflows",
    }
    reads = [
        "/passports",
        "/passports/{id}",
        "/passports/{id}/workflow",
        "/passports/{id}/notice-draft",
        "/passports/{id}/dossier",
        "/command-center/glossary",
        "/command-center/invoices/{id}/guide",
        "/product/portal",
        "/product/business",
        "/product/owner-summary",
        "/product/team",
        "/product/contributions",
        "/product/invoices/{id}/review-facts",
        "/product/invoices/{id}/traps",
        "/product/invoices/{id}/tax-suggestions",
        "/product/schemes",
        "/product/competitors",
        "/product/workflows",
        "/product/workflows/{id}",
        "/product/notifications",
        "/whatsapp",
        "/whatsapp/supplier-recipients",
    ]
    writes = [
        (
            "POST",
            "/passports/from-source",
            scope | {"purchase_import_id": identifier, "row_number": 1},
        ),
        (
            "POST",
            "/passports/intelligence",
            scope | {"question": "Saved facts only", "use_ai": False},
        ),
        ("POST", "/passports/{id}/confirm", version | {"fields": FIELDS}),
        (
            "POST",
            "/passports/{id}/evidence",
            version
            | {
                "kind": "PO",
                "reference": "TEST-ORDER",
                "taxable_value": "100000.00",
                "observed_on": "2024-05-10",
            },
        ),
        ("POST", "/passports/{id}/clocks", version),
        ("POST", "/passports/{id}/portal", version | {"import_id": identifier}),
        (
            "POST",
            "/passports/{id}/approve",
            version
            | {
                "source_signature": signature,
                "decision": "HOLD",
                "amount": "0.00",
                "reason": "Synthetic authority check",
            },
        ),
        ("POST", "/passports/{id}/resolution", version | {"action": "DRAFT"}),
        ("POST", "/passports/{id}/simulate-fetch", version | {"status": "MISSING"}),
        ("POST", "/passports/{id}/refresh", {}),
        ("POST", "/passports/{id}/retry-extraction", {}),
        (
            "POST",
            "/passports/{id}/scenario",
            version | {"cash_available": "1.00", "proposed_payment": "1.00"},
        ),
        ("POST", "/passports/{id}/watch", version | {"enabled": True}),
        (
            "POST",
            "/passports/{id}/notice-assistance",
            {"notice_text": "Synthetic notice for authority checking", "use_ai": False},
        ),
        ("POST", "/passports/{id}/details", version | {"items": []}),
        (
            "POST",
            "/passports/{id}/ims-review",
            version
            | {
                "source_signature": signature,
                "action": "HUMAN_REVIEW",
                "reason": "Synthetic authority check",
            },
        ),
        ("POST", "/passports/{id}/supplier-invite", version | {"phone": "+919876543210"}),
        ("POST", "/passports/{id}/supplier-send", version),
        (
            "POST",
            "/passports/{id}/demo-bank-payment",
            version | {"source_signature": signature, "amount": "1.00"},
        ),
        (
            "POST",
            "/product/business",
            scope | {"expected_version": 0, "profile": {"business_name": "Authority test"}},
        ),
        (
            "POST",
            "/product/team/members",
            {
                "username": "authnewuser",
                "password": "synthetic-only-password",
                "display_name": "Authority test",
                "roles": ["CA"],
            },
        ),
        ("PATCH", "/product/team/members/{id}", version | {"roles": ["CA"], "active": True}),
        (
            "POST",
            "/product/contributions",
            scope | {"role": "CA", "note": "Synthetic authority check"},
        ),
        (
            "POST",
            "/product/invoices/{id}/review-facts",
            version | {"source_signature": signature, "note": "Synthetic authority check"},
        ),
        (
            "POST",
            "/product/tax-suggestions/review",
            {
                "passport_id": identifier,
                "suggestion_id": "missing_gst",
                "fingerprint": signature,
                "conclusion": "MORE_EVIDENCE",
                "note": "Synthetic authority check",
            },
        ),
        (
            "POST",
            "/product/assistants/{id}",
            scope | {"question": "Saved facts only", "use_ai": False},
        ),
        ("POST", "/product/workflows", {"passport_id": identifier}),
        ("POST", "/product/workflows/{id}/refresh", {}),
        (
            "POST",
            "/product/nodes/{id}/assign",
            version | {"user_id": identifier, "note": "Synthetic authority check"},
        ),
        (
            "POST",
            "/product/nodes/{id}/transition",
            version
            | {
                "fingerprint": signature,
                "state": "IN_PROGRESS",
                "note": "Synthetic authority check",
            },
        ),
        ("POST", "/product/notifications/{id}/read", {}),
        ("POST", "/whatsapp/link-code", scope),
        ("POST", "/whatsapp/context", scope | version),
        ("POST", "/whatsapp/unlink", version),
        (
            "POST",
            "/whatsapp/supplier-consent-code",
            version | {"action_id": identifier, "draft_id": identifier},
        ),
        (
            "POST",
            "/whatsapp/supplier-followups",
            version | {"action_id": identifier, "draft_id": identifier, "recipient_id": identifier},
        ),
    ]
    return reads, writes, query_reads, scope
