"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { submitCaseAction } from "@/app/actions";
import { DEMO_FIXTURES } from "@/lib/demoFixtures";

export function NewCaseForm() {
  const router = useRouter();
  const [json, setJson] = useState(() => JSON.stringify(DEMO_FIXTURES[0]?.applicant, null, 2));
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function loadFixture(index: number) {
    const fixture = DEMO_FIXTURES[index];
    if (!fixture) return;
    setJson(JSON.stringify(fixture.applicant, null, 2));
    setError(null);
  }

  function submit() {
    setError(null);
    let parsed;
    try {
      parsed = JSON.parse(json);
    } catch {
      setError("Not valid JSON.");
      return;
    }
    startTransition(async () => {
      const result = await submitCaseAction(parsed);
      if (result.ok) {
        router.push(`/cases/${result.caseId}`);
      } else {
        setError(result.error);
      }
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {DEMO_FIXTURES.map((fixture, i) => (
          <button
            key={fixture.label}
            onClick={() => loadFixture(i)}
            className="rounded-lg border border-border bg-panel px-3 py-1.5 text-xs text-neutral-200 hover:border-gray-400 hover:text-white"
          >
            {fixture.label}
          </button>
        ))}
      </div>

      <textarea
        className="h-96 w-full rounded-lg border border-border bg-surface p-3 font-mono text-xs text-white"
        value={json}
        onChange={(e) => setJson(e.target.value)}
        spellCheck={false}
      />

      {error && <p className="text-sm text-red-400">{error}</p>}

      <button
        disabled={isPending}
        onClick={submit}
        className="rounded-lg border border-white/15 bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {isPending ? "Submitting…" : "Submit case"}
      </button>
    </div>
  );
}
