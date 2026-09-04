import { RecommendationBadge, RiskLevelBadge } from "@/components/Badges";
import type { SpecialistAnalysis } from "@/lib/types";

export function AnalysisCard({
  title,
  analysis,
  pending = false,
}: {
  title: string;
  analysis: SpecialistAnalysis | null;
  pending?: boolean;
}) {
  if (!analysis) {
    return (
      <div className="card">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-fg">{title}</h3>
          {pending && (
            <span className="flex h-2 w-2 rounded-full bg-subtle animate-pulse" aria-hidden />
          )}
        </div>
        {pending ? (
          <div className="mt-3 space-y-2" aria-live="polite">
            <div className="h-2 w-4/5 animate-pulse rounded bg-border" />
            <div className="h-2 w-3/5 animate-pulse rounded bg-border" />
            <p className="pt-1 text-xs text-muted">Analyzing…</p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted">Not yet completed.</p>
        )}
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        <div className="flex gap-2">
          <RiskLevelBadge level={analysis.risk_level} />
          <RecommendationBadge recommendation={analysis.recommendation} />
        </div>
      </div>
      <p className="text-sm leading-relaxed text-fg">{analysis.summary}</p>
      {analysis.key_factors.length > 0 && (
        <div>
          <p className="label mb-1">Key factors</p>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-muted">
            {analysis.key_factors.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      {analysis.conditions.length > 0 && (
        <div>
          <p className="label mb-1">Conditions</p>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-amber-300">
            {analysis.conditions.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
