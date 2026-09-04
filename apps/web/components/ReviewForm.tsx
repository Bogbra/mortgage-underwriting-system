"use client";

import { useState, useTransition } from "react";

import { reviewCaseAction } from "@/app/actions";

export function ReviewForm({ caseId }: { caseId: string }) {
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [isPending, startTransition] = useTransition();

  function submit(approve: boolean) {
    setError(null);
    startTransition(async () => {
      const result = await reviewCaseAction(caseId, approve, notes);
      if (result.ok) {
        setDone(true);
      } else {
        setError(result.error);
      }
    });
  }

  if (done) {
    return (
      <div className="card border-emerald-500/30 bg-emerald-500/10 text-sm text-emerald-300">
        Review recorded. Refresh to see the updated case status.
      </div>
    );
  }

  return (
    <div className="card space-y-3">
      <h3 className="text-sm font-semibold text-fg">Human-in-the-loop review</h3>
      <p className="text-sm text-muted">
        This case is flagged for senior underwriter review before it can be finalized.
      </p>
      <textarea
        className="w-full rounded-lg border border-border bg-bg p-3 text-sm text-fg placeholder:text-subtle"
        rows={3}
        placeholder="Reviewer notes (required)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex gap-3">
        <button
          disabled={isPending || notes.trim().length === 0}
          onClick={() => submit(true)}
          className="rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-300 ring-1 ring-inset ring-emerald-500/30 hover:bg-emerald-500/30 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={isPending || notes.trim().length === 0}
          onClick={() => submit(false)}
          className="rounded-lg bg-red-500/20 px-4 py-2 text-sm font-medium text-red-300 ring-1 ring-inset ring-red-500/30 hover:bg-red-500/30 disabled:opacity-50"
        >
          Uphold denial / reject
        </button>
      </div>
    </div>
  );
}
