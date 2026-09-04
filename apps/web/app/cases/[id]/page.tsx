import { notFound } from "next/navigation";

import { AnalysisCard } from "@/components/AnalysisCard";
import { AutoRefresh } from "@/components/AutoRefresh";
import { DecisionBadge, RiskScoreMeter, StatusBadge } from "@/components/Badges";
import { ReviewForm } from "@/components/ReviewForm";
import { ApiError, getCase } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let caseDetail;
  try {
    caseDetail = await getCase(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const { decision, critic_review: critic } = caseDetail;
  const isProcessing = caseDetail.status === "received" || caseDetail.status === "running";

  return (
    <div className="space-y-8">
      <AutoRefresh enabled={isProcessing} intervalMs={3000} />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white">{caseDetail.case_id}</h1>
          <p className="text-sm text-muted">{caseDetail.applicant_name}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={caseDetail.status} />
          {decision && <DecisionBadge decision={decision.decision} />}
        </div>
      </div>

      {isProcessing && (
        <div className="card flex items-center gap-3 border-gray-500/30 bg-gray-500/10">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gray-300 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-gray-300" />
          </span>
          <p className="text-sm text-neutral-200">
            Case received — specialist agents are analyzing now. This page updates automatically
            every few seconds.
          </p>
        </div>
      )}

      {caseDetail.error && (
        <div className="card border-red-500/30 bg-red-500/10 text-sm text-red-300">
          Workflow failed: {caseDetail.error}
        </div>
      )}

      {decision && (
        <div className="card space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-sm font-semibold text-white">Final decision</h2>
            <RiskScoreMeter score={decision.risk_score} />
          </div>
          <p className="whitespace-pre-line text-sm leading-relaxed text-neutral-200">
            {decision.credit_memo}
          </p>
          {decision.conditions.length > 0 && (
            <div>
              <p className="label mb-1">Conditions</p>
              <ul className="list-inside list-disc space-y-0.5 text-sm text-amber-300">
                {decision.conditions.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {caseDetail.bias_flags.length > 0 && (
        <div className="card border-amber-500/30 bg-amber-500/10 space-y-2">
          <h2 className="text-sm font-semibold text-amber-300">
            Fair-lending guardrail flags ({caseDetail.bias_flags.length})
          </h2>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-amber-200">
            {caseDetail.bias_flags.map((f, i) => (
              <li key={i}>{f.detail}</li>
            ))}
          </ul>
        </div>
      )}

      {caseDetail.status === "awaiting_human_review" && !caseDetail.human_review_completed && (
        <ReviewForm caseId={caseDetail.case_id} />
      )}

      {caseDetail.human_review_completed && (
        <div className="card space-y-1">
          <h2 className="text-sm font-semibold text-white">Reviewer notes</h2>
          <p className="text-sm text-neutral-200">{caseDetail.human_notes}</p>
        </div>
      )}

      <div>
        <h2 className="mb-3 text-sm font-semibold text-white">Specialist analyses</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <AnalysisCard title="Credit Analyst" analysis={caseDetail.credit_analysis} pending={isProcessing} />
          <AnalysisCard title="Income Analyst" analysis={caseDetail.income_analysis} pending={isProcessing} />
          <AnalysisCard title="Asset Analyst" analysis={caseDetail.asset_analysis} pending={isProcessing} />
          <AnalysisCard
            title="Collateral Analyst"
            analysis={caseDetail.collateral_analysis}
            pending={isProcessing}
          />
        </div>
      </div>

      {critic && (
        <div className="card space-y-2">
          <h2 className="text-sm font-semibold text-white">Critic synthesis</h2>
          <p className="text-sm text-neutral-200">{critic.synthesis}</p>
          {critic.issues.length > 0 && (
            <ul className="list-inside list-disc space-y-0.5 text-sm text-amber-300">
              {critic.issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="card">
        <h2 className="mb-2 text-sm font-semibold text-white">Audit trail</h2>
        {caseDetail.reasoning_chain.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gray-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-gray-400" />
            </span>
            Case received, waiting for the first agent to report in…
          </div>
        ) : (
          <ol className="space-y-1.5 text-sm text-muted">
            {caseDetail.reasoning_chain.map((step, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-white/30">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
            {isProcessing && (
              <li className="flex items-center gap-2 pt-1 text-white/40">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gray-400 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-gray-400" />
                </span>
                still working…
              </li>
            )}
          </ol>
        )}
      </div>
    </div>
  );
}
