import type { Context } from "./shared";
import { path } from "./shared";
export const productPath = (c: Context, suffix: string) =>
  path(c, `product/${suffix}`);
export const selection = (c: Context) =>
  `registration_id=${c.registration.id}&period=${c.period}`;
export type Member = {
  id: string;
  username: string;
  display_name: string;
  roles: string[];
  membership_role: string;
  active: boolean;
  version: number;
};
export type Portal = {
  owner: boolean;
  roles: string[];
  financial_write: boolean;
  account_limit: number;
};
export type Employee = {
  name: string;
  role: string;
  monthly_salary: string | null;
};
export type Profile = {
  business_name: string;
  business_type: string;
  workforce_count: number | null;
  employees?: Employee[];
  monthly_revenue: string | null;
  monthly_profit: string | null;
  monthly_operating_cost: string | null;
  tax_paid: Record<string, string | null>;
  msme_status: string;
  annual_turnover: string | null;
  loan_needed: string | null;
  prior_tarun_repaid: boolean | null;
  marketing_spend: string | null;
  attributed_sales: string | null;
  note: string;
  recorded_payroll_total?: string | null;
};
export type Business = {
  profile: Partial<Profile>;
  version: number;
  employee_details_visible: boolean;
  fingerprint: string;
};
export const teamRoles = [
  "CFO",
  "CMO",
  "CMA",
  "CA",
  "CEO",
  "COO",
  "CTO",
  "ACCOUNTS",
  "WAREHOUSE",
  "FOLLOWUP",
];
export const roleNames: Record<string, string> = {
  CFO: "Finance lead",
  CMO: "Marketing lead",
  CMA: "Cost and margin reviewer",
  CA: "Tax and accounting reviewer",
  CEO: "Business lead",
  COO: "Operations lead",
  CTO: "Technology lead",
  ACCOUNTS: "Accounts clerk",
  WAREHOUSE: "Purchase / warehouse",
  FOLLOWUP: "Supplier follow-up",
  OWNER: "Business owner",
  OBSERVER: "Observer",
};

export const presetTeamRoles = ["CA", "CFO", "CMA", "CMO", "CEO", "COO", "CTO"];
