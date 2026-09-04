import { NewCaseForm } from "@/components/NewCaseForm";

export default function NewCasePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Submit a new case</h1>
        <p className="text-sm text-muted">
          Load a sample applicant or paste applicant JSON, then submit. The workflow runs in the
          background — you&apos;ll land on the case detail page and can refresh to watch it progress.
        </p>
      </div>
      <div className="card">
        <NewCaseForm />
      </div>
    </div>
  );
}
