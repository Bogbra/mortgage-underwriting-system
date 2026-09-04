import type { ApplicantDataInput } from "./types";

/**
 * Demo convenience only — mirrors backend/data/test_cases/mortgage_test_cases.json
 * so the dashboard can offer one-click sample submissions without a file
 * upload flow. Not used by any test; the backend's copy is the source of
 * truth for the eval harness.
 */
export const DEMO_FIXTURES: { label: string; applicant: ApplicantDataInput }[] = [
  {
    label: "Strong applicant (expected: APPROVED)",
    applicant: {
      case_id: "CASE-2026-0001",
      name: "Sarah Johnson",
      ssn: "412-98-3305",
      phone: "312-555-0148",
      email: "sarah.johnson@example.com",
      address: "1847 Winslow Ave, Chicago, IL 60614",
      credit_score: 782,
      credit_history: { bankruptcies: 0, foreclosures: 0, late_payments_12mo: 0, collections: [] },
      employment: { type: "W2", years: 6, monthly_income: 11000, employer: "Meridian Health Systems" },
      debts: { car_loan: 380, student_loan: 210 },
      loan: { amount: 380000, down_payment: 95000, estimated_payment: 2450, use: "primary_residence" },
      assets: {
        checking: 22000,
        savings: 98000,
        recent_deposits: [
          { amount: 2200, date: "2026-06-15", explanation: "Annual performance bonus, paystub attached" },
        ],
      },
      property: { type: "single_family", appraised_value: 480000, condition: "good, no deferred maintenance noted" },
    },
  },
  {
    label: "Marginal applicant (expected: CONDITIONAL_APPROVAL)",
    applicant: {
      case_id: "CASE-2026-0002",
      name: "Michael Chen",
      ssn: "556-71-2290",
      phone: "415-555-0176",
      email: "michael.chen@example.com",
      address: "902 Fremont St, San Jose, CA 95112",
      credit_score: 668,
      credit_history: {
        bankruptcies: 0,
        foreclosures: 0,
        late_payments_12mo: 2,
        collections: ["Medical collection, $450, opened 2025"],
      },
      employment: { type: "self_employed", years: 3, monthly_income: 7200, employer: "Chen Consulting LLC" },
      debts: { auto_loan: 520, credit_card_minimum: 310, personal_loan: 275 },
      loan: { amount: 340000, down_payment: 34000, estimated_payment: 2380, use: "primary_residence" },
      assets: {
        checking: 9200,
        savings: 30000,
        recent_deposits: [
          { amount: 6000, date: "2026-07-01", explanation: "Client invoice payment; sourcing not yet documented" },
        ],
      },
      property: { type: "condominium", appraised_value: 395000, condition: "fair, minor deferred maintenance noted" },
    },
  },
  {
    label: "Weak applicant (expected: DENIED)",
    applicant: {
      case_id: "CASE-2026-0003",
      name: "Robert Martinez",
      ssn: "298-44-1187",
      phone: "702-555-0193",
      email: "robert.martinez@example.com",
      address: "5510 Desert Bloom Ct, Las Vegas, NV 89147",
      credit_score: 588,
      credit_history: {
        bankruptcies: 1,
        foreclosures: 0,
        late_payments_12mo: 5,
        collections: ["Credit card collection, $2,300, opened 2025", "Utility collection, $310, opened 2024"],
      },
      employment: { type: "W2", years: 0.8, monthly_income: 4800, employer: "Coastal Retail Group" },
      debts: { auto_loan: 410, credit_card_minimum_1: 260, credit_card_minimum_2: 180 },
      loan: { amount: 285000, down_payment: 15000, estimated_payment: 2050, use: "primary_residence" },
      assets: {
        checking: 1200,
        savings: 1800,
        recent_deposits: [{ amount: 2600, date: "2026-06-20", explanation: "Cash deposit, source undocumented" }],
      },
      property: { type: "single_family", appraised_value: 292000, condition: "fair, roof repair flagged in appraisal" },
    },
  },
];
