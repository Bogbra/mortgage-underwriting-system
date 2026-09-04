import type { CaseStatus, FinalDecision, Recommendation, RiskLevel } from "@/lib/types";

const STATUS_STYLES: Record<CaseStatus, string> = {
  // Neutral progress states — not risk signals, so these use the shared
  // chrome palette rather than the semantic red/amber/green used below.
  received: "bg-secondary text-muted ring-border-strong",
  running: "bg-gold/15 text-gold-hover ring-gold/30",
  awaiting_human_review: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  completed: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  failed: "bg-red-500/15 text-red-300 ring-red-500/30",
};

const DECISION_STYLES: Record<FinalDecision, string> = {
  APPROVED: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  CONDITIONAL_APPROVAL: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  DENIED: "bg-red-500/15 text-red-300 ring-red-500/30",
};

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  MEDIUM: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  HIGH: "bg-red-500/15 text-red-300 ring-red-500/30",
};

const RECOMMENDATION_STYLES: Record<Recommendation, string> = {
  PASS: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  CONDITIONAL: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  FAIL: "bg-red-500/15 text-red-300 ring-red-500/30",
};

function Badge({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}>
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  return <Badge className={STATUS_STYLES[status]}>{status.replaceAll("_", " ")}</Badge>;
}

export function DecisionBadge({ decision }: { decision: FinalDecision }) {
  return <Badge className={DECISION_STYLES[decision]}>{decision.replaceAll("_", " ")}</Badge>;
}

export function RiskLevelBadge({ level }: { level: RiskLevel }) {
  return <Badge className={RISK_STYLES[level]}>{level} risk</Badge>;
}

export function RecommendationBadge({ recommendation }: { recommendation: Recommendation }) {
  return <Badge className={RECOMMENDATION_STYLES[recommendation]}>{recommendation}</Badge>;
}

export function RiskScoreMeter({ score }: { score: number }) {
  const tone = score >= 65 ? "bg-red-400" : score >= 31 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-32 overflow-hidden rounded-full bg-border">
        <div className={`h-full ${tone}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm text-fg">{score}/100</span>
    </div>
  );
}
