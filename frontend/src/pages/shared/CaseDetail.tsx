import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Circle, Edit3, FileSearch, Landmark, Loader2, ScrollText, Stamp, UserCheck } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { fmtDateTime, humanize } from "../../lib/format";
import type { FDRDetail } from "../../lib/types";
import { AuditTimeline, DocumentList, FactGrid, StatusTracker, ValidationList } from "../../components/fdr";
import { BankSimulator, ReviewActions } from "../../components/actions";
import { Alert, Card, EmptyState, ErrorState, Field, PageHeader, SimulatedTag, Spinner, StatusBadge, useToast } from "../../components/ui";

const TABS = [
  { key: "overview", label: "Overview", icon: FileSearch },
  { key: "bank", label: "Bank verification", icon: Landmark },
  { key: "clearance", label: "Clearance", icon: Stamp },
  { key: "audit", label: "Audit timeline", icon: ScrollText },
];

export default function CaseDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "overview";
  const { data: fdr, loading, error, reload } = useFetch<FDRDetail>(`/fdrs/${id}`);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const role = user.role;
  const reviewer = role === "officer" || role === "senior";
  const listPath = role === "institution" ? "/institution/fdrs" : `/${role}/cases`;

  if (loading && !fdr) return <Spinner />;
  if (error || !fdr) return <ErrorState message={error || "Not found"} onRetry={reload} />;

  const assign = async () => {
    try {
      await api.post(`/fdrs/${fdr.id}/assign`);
      toast("success", "Case assigned to you.");
      reload();
    } catch (e) {
      toast("error", errorMessage(e));
    }
  };

  const requestClearance = async () => {
    setBusy(true);
    try {
      await api.post(`/fdrs/${fdr.id}/clearance-requests`, { reason });
      toast("success", "Clearance request submitted to AICTE.");
      setReason("");
      reload();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const openCr = fdr.clearance_requests.find((c) => ["pending_officer_review", "recommended_approval", "recommended_rejection"].includes(c.status));

  return (
    <div>
      <Link to={listPath} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-700"><ArrowLeft className="h-4 w-4" />Back to list</Link>
      <PageHeader title={fdr.reference_no}
        subtitle={<span className="flex flex-wrap items-center gap-2">{fdr.institution_name} · <span className="font-mono">{fdr.fdr_number || "no FDR number"}</span> <StatusBadge kind="stage" value={fdr.stage} /></span>}
        actions={<>
          {role === "institution" && ["draft", "correction_requested"].includes(fdr.submission_status) && (
            <Link to={`/institution/upload/${fdr.id}`} className="btn-teal"><Edit3 className="h-4 w-4" />{fdr.submission_status === "draft" ? "Continue draft" : "Make corrections"}</Link>
          )}
          {reviewer && <Link to={`/${role}/cases/${fdr.id}/ocr`} className="btn-outline"><FileSearch className="h-4 w-4" />OCR review</Link>}
          {reviewer && fdr.assigned_officer_id !== user.id && <button className="btn-outline" onClick={assign}><UserCheck className="h-4 w-4" />Assign to me</button>}
        </>} />

      <Card className="mb-6"><StatusTracker fdr={fdr} /></Card>

      {fdr.submission_status === "correction_requested" && <div className="mb-4"><Alert tone="warning" title="Correction requested">{fdr.last_review_remarks}</Alert></div>}
      {fdr.is_cleared && (
        <div className="mb-4"><Alert tone="success" title="Clearance approved (demonstration workflow)">
          The approval is recorded in SurakshaFD. It does <b>not</b> transfer or release any bank funds; actual release happens outside this system.
        </Alert></div>
      )}

      <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setParams({ tab: t.key }, { replace: true })}
            className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition ${tab === t.key ? "border-teal-600 text-navy-900" : "border-transparent text-slate-500 hover:text-navy-700"}`}>
            <t.icon className="h-4 w-4" />{t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card title="Deposit details" subtitle="As entered and confirmed by the institution"><FactGrid fdr={fdr} /></Card>
            <Card title="Automatic validation" subtitle="Latest run · warnings need human review and are never automatic rejections">
              <ValidationList items={fdr.validation_results} />
            </Card>
          </div>
          <div className="space-y-6">
            {reviewer && (
              <Card title="Document review" subtitle={fdr.review_due_at ? `Review due ${fmtDateTime(fdr.review_due_at)}` : undefined}>
                <ReviewActions fdr={fdr} onDone={reload} />
                {fdr.last_review_remarks && <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600"><b>Last remarks:</b> {fdr.last_review_remarks}</div>}
              </Card>
            )}
            <Card title="Documents"><DocumentList docs={fdr.documents} required={fdr.required_documents} /></Card>
          </div>
        </div>
      )}

      {tab === "bank" && (
        <div className="grid gap-6 lg:grid-cols-2">
          {reviewer && <Card title="Bank Verification Simulator"><BankSimulator fdr={fdr} onDone={reload} /></Card>}
          <Card title="Verification history" subtitle="Document-check status and bank-verification status are tracked separately" className={reviewer ? "" : "lg:col-span-2"}>
            <div className="mb-4 flex flex-wrap gap-4 text-sm">
              <div>Document status: <StatusBadge kind="document" value={fdr.document_status} /></div>
              <div>Bank status: <StatusBadge kind="bank" value={fdr.bank_status} /></div>
            </div>
            {fdr.bank_verifications.length ? (
              <ul className="space-y-3">
                {fdr.bank_verifications.map((v) => (
                  <li key={v.id} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge kind="bank" value={v.outcome} />
                      {v.is_simulated && <SimulatedTag />}
                      <span className="ml-auto text-xs text-slate-400">{fmtDateTime(v.created_at)}</span>
                    </div>
                    <div className="mt-2 text-sm text-slate-700">{v.remarks}</div>
                    <div className="mt-1 text-xs text-slate-500">{v.response_summary}</div>
                    <div className="mt-1 text-xs text-slate-500">Ref <span className="font-mono">{v.reference}</span> · adapter {v.adapter} · by {v.officer}{v.evidence_document_id ? " · evidence attached" : ""}</div>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No verification attempts yet" />}
          </Card>
        </div>
      )}

      {tab === "clearance" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Clearance prerequisites" subtitle="Set by the clearance policy (demo values)">
            <ul className="space-y-2">
              {fdr.eligibility.checks.map((c) => (
                <li key={c.code} className="flex items-center gap-2 text-sm">
                  {c.ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Circle className="h-4 w-4 text-slate-300" />}
                  <span className={c.ok ? "text-slate-700" : "text-slate-500"}>{c.label}</span>
                </li>
              ))}
            </ul>
            {role === "institution" && (
              <div className="mt-5 border-t border-slate-100 pt-4">
                {fdr.eligibility.eligible ? (
                  <>
                    <Field label="Reason for clearance request">
                      <textarea className="input min-h-[90px]" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. FDR has matured and approval conditions are complete; requesting clearance." />
                    </Field>
                    <button className="btn-teal mt-3 w-full" disabled={busy || reason.trim().length < 5} onClick={requestClearance}>
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Stamp className="h-4 w-4" />}Submit clearance request
                    </button>
                  </>
                ) : (
                  <Alert tone="info">{openCr ? "A clearance request is already in progress." : fdr.is_cleared ? "This FDR has been cleared." : "Clearance can be requested once all prerequisites above are met."}</Alert>
                )}
              </div>
            )}
          </Card>
          <Card title="Clearance requests">
            {fdr.clearance_requests.length ? (
              <ul className="space-y-3">
                {fdr.clearance_requests.map((c) => (
                  <li key={c.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge kind="clearance" value={c.status} />
                      <span className="ml-auto text-xs text-slate-400">{fmtDateTime(c.created_at)}</span>
                    </div>
                    <div className="mt-2 text-slate-700">{c.reason}</div>
                    {c.recommendation && <div className="mt-2 text-xs text-slate-600"><b>Officer ({c.recommended_by}):</b> recommends {c.recommendation}: {c.recommendation_remarks}</div>}
                    {c.decisions.map((d) => <div key={d.id} className="mt-1 text-xs text-slate-600"><b>Final decision ({d.decided_by}):</b> {humanize(d.decision)}: {d.remarks}</div>)}
                    {role === "officer" && c.status === "pending_officer_review" && <Link to={`/officer/clearances/${c.id}`} className="btn-primary btn-sm mt-3">Review request</Link>}
                    {role === "senior" && c.status.startsWith("recommended") && <Link to={`/senior/decisions/${c.id}`} className="btn-primary btn-sm mt-3">Record decision</Link>}
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No clearance requests" />}
          </Card>
        </div>
      )}

      {tab === "audit" && (
        <Card title="Audit timeline" subtitle="Append-only record of every action on this case">
          <AuditTimeline entries={fdr.audit} />
        </Card>
      )}
    </div>
  );
}
