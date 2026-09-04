export type CaseStatus =
  | "received"
  | "running"
  | "awaiting_human_review"
  | "completed"
  | "failed";

export type FinalDecision = "APPROVED" | "CONDITIONAL_APPROVAL" | "DENIED";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type Recommendation = "PASS" | "CONDITIONAL" | "FAIL";

export interface CaseSummary {
  case_id: string;
  status: CaseStatus;
  applicant_name_redacted: string;
  risk_score: number | null;
  final_decision: FinalDecision | null;
  human_review_required: boolean;
  human_review_completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpecialistAnalysis {
  summary: string;
  risk_level: RiskLevel;
  recommendation: Recommendation;
  key_factors: string[];
  conditions: string[];
}

export interface CriticReview {
  consistent: boolean;
  issues: string[];
  synthesis: string;
  preliminary_risk_score: number;
}

export interface DecisionOutcome {
  risk_score: number;
  decision: FinalDecision;
  conditions: string[];
  credit_memo: string;
}

export interface BiasFlag {
  code: string;
  detail: string;
}

export interface CaseDetail {
  case_id: string;
  status: CaseStatus;
  human_review_required: boolean;
  human_review_completed: boolean;
  human_notes: string | null;
  human_reviewer: string | null;
  sanitized_data: Record<string, unknown>;
  credit_analysis: SpecialistAnalysis | null;
  income_analysis: SpecialistAnalysis | null;
  asset_analysis: SpecialistAnalysis | null;
  collateral_analysis: SpecialistAnalysis | null;
  critic_review: CriticReview | null;
  decision: DecisionOutcome | null;
  bias_flags: BiasFlag[];
  policy_violations: string[];
  reasoning_chain: string[];
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicantDataInput {
  case_id: string;
  name: string;
  ssn: string;
  phone: string;
  email?: string;
  address: string;
  credit_score: number;
  credit_history?: {
    bankruptcies?: number;
    foreclosures?: number;
    late_payments_12mo?: number;
    collections?: string[];
  };
  employment: {
    type: string;
    years: number;
    monthly_income: number;
    employer?: string;
  };
  debts?: Record<string, number>;
  loan: {
    amount: number;
    down_payment: number;
    estimated_payment: number;
    use?: string;
  };
  assets?: {
    checking?: number;
    savings?: number;
    recent_deposits?: { amount: number; date: string; explanation?: string }[];
  };
  property: {
    type: string;
    appraised_value: number;
    condition: string;
  };
}
