"""Plain-language knowledge: help never grants authority or decides eligibility."""

SECTION16 = "https://taxinformation.cbic.gov.in/content-page/explore-act/1000285/1000001"
MSME = "https://www.incometaxindia.gov.in/w/section-43b-39"
RULES = "https://taxinformation.cbic.gov.in/"

GLOSSARY = [
    {
        "term": "Invoice",
        "meaning": "The supplier bill: what they charged, when and for which goods.",
    },
    {"term": "PO", "meaning": "Purchase order: what your business agreed to buy."},
    {"term": "GRN", "meaning": "Goods receipt: what your warehouse records as received."},
    {
        "term": "GST statement / GSTR-2B",
        "meaning": "The received tax-side statement compared with your purchase records.",
    },
    {
        "term": "GSTIN",
        ("meaning"): (
            "A business GST registration number. Format alone does not prove active registration."
        ),
    },
    {
        "term": "ITC",
        ("meaning"): (
            "Input tax credit: purchase tax that may qualify for credi"
            "t after the applicable conditions are checked."
        ),
        "reference": "CGST Section 16",
        "source": SECTION16,
    },
    {
        "term": "IRN",
        ("meaning"): (
            "An e-invoice reference. A 64-hex string is only a format check, not authenticity."
        ),
        "reference": "CGST Rule 48(4)",
        "source": RULES,
    },
    {
        "term": "MSME payment timing",
        ("meaning"): (
            "Micro/small supplier payment terms need review. Record cl"
            "assification, acceptance and agreed dates; 45 days is not"
            " a universal deadline for every supplier."
        ),
        "reference": "MSMED Act Section 15",
        "source": MSME,
    },
    {
        "term": "43B(h)",
        ("meaning"): (
            "A payment-timing deduction review for applicable micro/sm"
            "all suppliers, not an automatic 30% penalty."
        ),
        "reference": "Income-tax Act Section 43B(h)",
        "source": MSME,
    },
    {
        "term": "Rule 37A",
        ("meaning"): (
            "Track recorded credit reversal and later supplier-filing "
            "evidence for possible reclaim review."
        ),
        "reference": "CGST Rule 37A",
        "source": "https://gstcouncil.gov.in/sites/default/files/2024-05/ct26-2022.pdf",
    },
    {
        "term": "DRC-01C",
        ("meaning"): (
            "A tax-credit difference intimation that needs its actual notice and response facts."
        ),
        "reference": "CGST Rule 88D",
        "source": "https://gstcouncil.gov.in/sites/default/files/2024-05/gst-ct-38-2023.pdf",
    },
    {
        "term": "Tax under review",
        "meaning": "Recorded tax needing investigation; it is not proven loss.",
    },
    {
        "term": "Stale approval",
        "meaning": "Evidence changed after the decision. Review it again before release.",
    },
]
for entry in GLOSSARY:
    if "reference" in entry:
        entry["review"] = "NEEDS_CA_REVIEW"
        entry["review_note"] = "Verify with CA using the actual transaction and current rule."


def guide(view, can_write):
    """A read-only checklist over current evidence, never an approval mutation."""
    finding, approval = view["findings"], view["approval"]
    correction = view["resolution"].get("state", "NOT_STARTED")
    checks = [
        (
            "confirm",
            "Check the invoice",
            bool(view["confirmed"]),
            "AI proposes details; your confirmation establishes the saved bill facts.",
            "Accounts clerk",
        ),
        (
            "po",
            "Add the order items",
            finding["po"] == "MATCHED",
            "A bill alone cannot prove what your business agreed to buy.",
            "Purchase / warehouse",
        ),
        (
            "receipt",
            "Add the received items",
            finding["receipt"] == "MATCHED",
            "An order alone cannot prove that the goods arrived.",
            "Purchase / warehouse",
        ),
        (
            "gst",
            "Review the GST record",
            finding["gst"] == "MATCHED",
            "Compare the saved tax statement instead of assuming the supplier reported the bill.",
            "Finance reviewer",
        ),
        (
            "payment_facts",
            "Record what was already paid",
            view["gate"]["payment_facts_confirmed"],
            "Zero paid and unknown paid are different facts.",
            "Finance reviewer",
        ),
        (
            "decision",
            "Review the payment decision",
            bool(approval and approval["state"] == "APPROVED"),
            (
                "Approval must use the current evidence; recommendatio"
                "ns alone do not authorize release."
            ),
            "Finance reviewer",
        ),
        (
            "correction",
            "Track any supplier correction",
            finding["summary"] == "MATCHED" or correction == "RESOLVED",
            "A supplier promise needs supporting evidence before a correction is verified.",
            "Vendor follow-up",
        ),
    ]
    steps = [
        {
            "id": key,
            "title": title,
            "state": "DONE" if done else "NEEDS_ATTENTION",
            "why": why,
            "staff": staff,
        }
        for key, title, done, why, staff in checks
    ]
    next_step = next((step for step in steps if step["state"] != "DONE"), None)
    staff = [
        {
            "name": name,
            "scope": scope,
            "tasks": [
                step["title"] for step in steps if step["staff"] == name and step["state"] != "DONE"
            ],
        }
        for name, scope in [
            ("Accounts clerk", "Invoice intake and proposed fields"),
            ("Purchase / warehouse", "Saved order and receipt facts"),
            ("Finance reviewer", "Recorded tax, payment facts and deliberate decisions"),
            ("Vendor follow-up", "Saved requests, promises and supporting corrections"),
            ("Owner briefing", "Current priorities and missing evidence"),
        ]
    ]
    return {
        "passport_id": view["id"],
        "version": view["version"],
        "source_signature": view["source_signature"],
        "can_change": can_write,
        "steps": steps,
        "next_step": next_step,
        "staff": staff,
        "recorded_tax_under_review": view["gate"]["recorded_tax_under_review"],
        "mode": "SAVED_FACTS_ONLY",
        ("example"): (
            "10 pumps: goods INR 100000, recorded tax INR 18000, invoi"
            "ce total INR 118000. The order, delivery and tax statemen"
            "t are separate evidence."
        ),
    }
