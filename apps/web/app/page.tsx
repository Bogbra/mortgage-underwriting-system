import Link from "next/link";

import { DecisionBadge, StatusBadge } from "@/components/Badges";
import { listCases } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CasesPage() {
  const cases = await listCases();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-fg">Case queue</h1>
          <p className="text-sm text-muted">
            {cases.length} case{cases.length === 1 ? "" : "s"} — newest first
          </p>
        </div>
      </div>

      {cases.length === 0 ? (
        <div className="card text-sm text-muted">
          No cases yet. Submit one from <Link href="/new" className="text-muted underline hover:text-fg">New case</Link>.
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Case</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Human review</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.case_id} className="border-b border-border/60 last:border-0 hover:bg-accent-soft">
                  <td className="px-4 py-3">
                    <Link href={`/cases/${c.case_id}`} className="font-medium text-fg hover:text-muted">
                      {c.case_id}
                    </Link>
                    <div className="text-xs text-muted">{c.applicant_name}</div>
                    {c.possible_duplicate_of && (
                      <div className="text-xs text-amber-300">
                        ⚠ possible duplicate of {c.possible_duplicate_of}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3">
                    {c.final_decision ? <DecisionBadge decision={c.final_decision} /> : <span className="text-muted">—</span>}
                  </td>
                  <td className="px-4 py-3 text-fg">{c.risk_score ?? "—"}</td>
                  <td className="px-4 py-3">
                    {c.human_review_required ? (
                      <span className={c.human_review_completed ? "text-emerald-300" : "text-amber-300"}>
                        {c.human_review_completed ? "reviewed" : "pending"}
                      </span>
                    ) : (
                      <span className="text-muted">not required</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted">{new Date(c.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
