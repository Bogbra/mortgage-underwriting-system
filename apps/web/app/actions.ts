"use server";

import { revalidatePath } from "next/cache";

import { reviewCase, submitCase } from "@/lib/api";
import type { ApplicantDataInput } from "@/lib/types";

export async function submitCaseAction(
  applicant: ApplicantDataInput,
): Promise<{ ok: true; caseId: string } | { ok: false; error: string }> {
  try {
    const result = await submitCase(applicant);
    revalidatePath("/");
    return { ok: true, caseId: result.case_id };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Submission failed." };
  }
}

export async function reviewCaseAction(
  caseId: string,
  approve: boolean,
  notes: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await reviewCase(caseId, { approve, notes });
    revalidatePath(`/cases/${caseId}`);
    revalidatePath("/");
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Review failed." };
  }
}
