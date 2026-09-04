import "server-only";

import type { ApplicantDataInput, CaseDetail, CaseSummary } from "./types";

/**
 * All backend calls happen here, and only here, on the server (Next.js
 * Server Components / Server Actions). The bearer token never reaches the
 * browser — the client only ever talks to this app's own server, which is
 * the point of the `server-only` import above: it makes accidentally
 * importing this module from a Client Component a build error, not a leaked
 * secret.
 */

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";
const CALLER_TOKEN = process.env.BACKEND_API_TOKEN ?? "dev-local-token";
const REVIEWER_TOKEN = process.env.BACKEND_REVIEWER_TOKEN ?? "dev-reviewer-token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token = CALLER_TOKEN, ...rest } = init;
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...rest,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(rest.body ? { "Content-Type": "application/json" } : {}),
      ...rest.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body || response.statusText);
  }
  if (response.status === 202 || response.status === 204) {
    return response.json().catch(() => undefined) as Promise<T>;
  }
  return response.json() as Promise<T>;
}

export function listCases(): Promise<CaseSummary[]> {
  return request<CaseSummary[]>("/cases");
}

export function getCase(caseId: string): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`);
}

export function submitCase(
  applicant: ApplicantDataInput,
): Promise<{ case_id: string; status: string }> {
  return request(`/cases`, { method: "POST", body: JSON.stringify(applicant) });
}

export function reviewCase(
  caseId: string,
  decision: { approve: boolean; notes: string },
): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}/review`, {
    method: "POST",
    body: JSON.stringify(decision),
    token: REVIEWER_TOKEN,
  });
}
