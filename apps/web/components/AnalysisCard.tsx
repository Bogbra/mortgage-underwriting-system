import { RecommendationBadge, RiskLevelBadge } from "@/components/Badges";
import type { SpecialistAnalysis } from "@/lib/types";

export function AnalysisCard({
  title,
  analysis,
}: {
  title: string;
  analysis: SpecialistAnalysis | null;
}) {
  if (!analysis) {
    return (
      <div className="card">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="mt-2 text-sm text-muted">Not yet completed.</p>
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <div className="flex gap-2">
          <RiskLevelBadge level={analysis.risk_level} />
          <RecommendationBadge recommendation={analysis.recommendation} />
        </div>
      </div>
      <p className="text-sm leading-relaxed text-neutral-200">{analysis.summary}</p>
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
