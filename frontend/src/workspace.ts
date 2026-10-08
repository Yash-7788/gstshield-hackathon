export const workspaceSections = [
  "Today",
  "Owner desk",
  "Team desk",
  "Assistants",
  "Shared process",
  "Invoice desk",
  "Sources",
  "Reconciliation",
  "Cases & evidence",
  "Work queue",
  "Payment drafts",
  "Reports",
  "WhatsApp",
  "Business setup",
];
export const roleDesks: Record<
  string,
  { title: string; purpose: string; action: string; primary: string[] }
> = {
  OWNER: {
    title: "See the business. Choose the next step.",
    purpose:
      "Your figures, your team's progress and the bills that need a decision.",
    action: "Owner desk",
    primary: ["Owner desk", "Team desk"],
  },
  CA: {
    title: "The review desk.",
    purpose:
      "Bring in invoices, compare the supporting records and leave a review your team can follow.",
    action: "Invoice desk",
    primary: ["Team desk", "Invoice desk", "Assistants"],
  },
  CFO: {
    title: "Before money moves.",
    purpose:
      "Review tax needing attention, payment proposals and the evidence behind each choice.",
    action: "Invoice desk",
    primary: ["Team desk", "Invoice desk", "Assistants"],
  },
  CMA: {
    title: "Know your costs.",
    purpose:
      "Use supplied cost figures and confirmed invoice facts. Missing figures stay unknown.",
    action: "Assistants",
    primary: ["Team desk", "Assistants"],
  },
  CMO: {
    title: "See what comes back.",
    purpose:
      "See reported spend and attributed sales, then share what your finance team needs to know.",
    action: "Assistants",
    primary: ["Team desk", "Assistants"],
  },
  CEO: {
    title: "Your business, today.",
    purpose:
      "Read the business summary and the work your team has actually recorded.",
    action: "Assistants",
    primary: ["Team desk", "Assistants"],
  },
  COO: {
    title: "Keep work moving.",
    purpose:
      "Find the missing order or delivery record and see where the shared process is waiting.",
    action: "Assistants",
    primary: ["Team desk", "Assistants"],
  },
  CTO: {
    title: "Know what’s connected.",
    purpose:
      "Review saved application facts and integration limits. Firm infrastructure is not connected.",
    action: "Assistants",
    primary: ["Team desk", "Assistants"],
  },
  ACCOUNTS: {
    title: "Start with the bill.",
    purpose:
      "Capture supplier invoices and hand confirmed facts to the reviewer.",
    action: "Invoice desk",
    primary: ["Team desk", "Invoice desk"],
  },
  WAREHOUSE: {
    title: "Check what arrived.",
    purpose:
      "See which order and receipt facts are still needed for the invoice review.",
    action: "Invoice desk",
    primary: ["Team desk", "Invoice desk"],
  },
  FOLLOWUP: {
    title: "Get the correction.",
    purpose:
      "Track requests and responses. A supplier promise becomes a correction only after rechecking.",
    action: "Invoice desk",
    primary: ["Team desk", "Invoice desk"],
  },
  OBSERVER: {
    title: "Follow your team’s work.",
    purpose:
      "View shared progress and supporting records without making a financial decision.",
    action: "Team desk",
    primary: ["Team desk"],
  },
};
export function deskFor(role?: string) {
  return roleDesks[role || "OBSERVER"] || roleDesks.OBSERVER;
}

export const roleSections: Record<string, string[]> = {
  OWNER: ["Owner desk", "Team desk", "Business setup"],
  CA: [
    "Team desk",
    "Invoice desk",
    "Shared process",
    "Sources",
    "Reconciliation",
    "Cases & evidence",
    "Reports",
    "Assistants",
  ],
  CFO: [
    "Team desk",
    "Invoice desk",
    "Shared process",
    "Payment drafts",
    "Reports",
    "Assistants",
  ],
  CMA: ["Team desk", "Assistants"],
  CMO: ["Team desk", "Assistants"],
  CEO: ["Team desk", "Assistants"],
  COO: ["Team desk", "Assistants"],
  CTO: ["Team desk", "Assistants"],
  ACCOUNTS: ["Team desk", "Invoice desk", "Sources"],
  WAREHOUSE: ["Team desk", "Invoice desk"],
  FOLLOWUP: ["Team desk", "Invoice desk", "WhatsApp"],
  OBSERVER: ["Team desk"],
  ROLE_SETUP_REQUIRED: ["Team desk"],
};
export function sectionsFor(role?: string) {
  return roleSections[role || "OBSERVER"] || roleSections.OBSERVER;
}
export function homeFor(role?: string) {
  return role === "OWNER" ? "Owner desk" : "Team desk";
}
