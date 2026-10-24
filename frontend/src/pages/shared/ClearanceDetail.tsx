import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Ban, CheckCircle2, Circle, Gavel, Loader2, ShieldAlert, ThumbsDown, ThumbsUp, XCircle } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { fmtDateTime, humanize } from "../../lib/format";
import type { Clearance, FDRDetail } from "../../lib/types";
import { AuditTimeline, DocumentList, FactGrid, StatusTracker, ValidationList } from "../../components/fdr";
import { Alert, Card, ErrorState, Field, PageHeader, SimulatedTag, Spinner, StatusBadge, useToast } from "../../components/ui";

/** Officer: Clearance Review (recommend). Senior: Decision Details (final decision). */
export default function ClearanceDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { data: cr, loading, error, reload } = useFetch<Clearance>(`/clearance-requests/${id}`);
  const { data: fdr, reload: reloadFdr } = useFetch<FDRDetail>(cr ? `/fdrs/${cr.fdr_id}` : null);
  const [choice, setChoice] = useState<"approve" | "reject" | null>(null);
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  if (loading && !cr) return <Spinner />;
  if (error || !cr) return <ErrorState message={error || "Not found"} onRetry={reload} />;

  const isSenior = user.role === "senior";
  const canRecommend = (user.role === "officer" || isSenior) && cr.status === "pending_officer_review";
  const awaitingDecision = cr.status === "recommended_approval" || cr.status === "recommended_rejection";
  const selfRecommended = cr.recommended_by_id === user.id;
  const canDecide = isSenior && awaitingDecision && !selfRecommended;
  const minLen = canDecide ? 10 : 5;

  const submit = async () => {
    setBusy(true);
    try {
      if (canDecide) {
        await api.post(`/clearance-requests/${cr.id}/decide`, { decision: choice === "approve" ? "approved" : "rejected", remarks });
        toast("success", `Final decision recorded: ${choice === "approve" ? "approved" : "rejected"} (demo).`);
      } else {
        await api.post(`/clearance-requests/${cr.id}/recommend`, { recommendation: choice, remarks });
        toast("success", "Recommendation sent to a senior approving officer.");
      }
      setChoice(null);
      setRemarks("");
      reload();
      reloadFdr();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const back = isSenior ? "/senior/approvals" : "/officer/clearances";
  const prereq = cr.current_eligibility?.checks.filter((c) => c.code !== "NO_OPEN_REQUEST") || [];

  return (
    <div>
      <Link to={back} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-700"><ArrowLeft className="h-4 w-4" />Back</Link>
      <PageHeader title={`${isSenior ? "Decision" : "Clearance Review"} · CR-${String(cr.id).padStart(4, "0")}`}
        subtitle={<span className="flex flex-wrap items-center gap-2">{cr.fdr?.reference_no} · {cr.fdr?.institution_name} <StatusBadge kind="clearance" value={cr.status} /></span>}
        actions={<Link to={`/${user.role}/cases/${cr.fdr_id}`} className="btn-outline">Open full case</Link>} />

      {fdr && <Card className="mb-6"><StatusTracker fdr={fdr} /></Card>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Request" subtitle={`By ${cr.requested_by} · ${fmtDateTime(cr.created_at)}`}>
            <p className="text-sm text-slate-700">{cr.reason}</p>
            {cr.recommendation && (
              <div className={`mt-4 rounded-lg border p-3 text-sm ${cr.recommendation === "approve" ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
                <div className="font-semibold">Officer recommendation: {cr.recommendation === "approve" ? "APPROVE" : "REJECT"}</div>
                <div className="mt-1 text-slate-700">{cr.recommendation_remarks}</div>
                <div className="mt-1 text-xs text-slate-500">{cr.recommended_by} · {fmtDateTime(cr.recommended_at)}</div>
              </div>
            )}
            {cr.decisions.map((d) => (
              <div key={d.id} className="mt-3 rounded-lg border border-navy-200 bg-navy-50 p-3 text-sm">
                <div className="font-semibold">Final decision: {humanize(d.decision)} (demo)</div>
                <div className="mt-1">{d.remarks}</div>
                <div className="mt-1 text-xs text-slate-500">{d.decided_by} · {fmtDateTime(d.created_at)}</div>
              </div>
            ))}
          </Card>
          {fdr && <Card title="Deposit details"><FactGrid fdr={fdr} /></Card>}
          {fdr && (
            <Card title="Verification evidence">
              <div className="mb-3 grid gap-3 sm:grid-cols-2">
                <div className="text-sm">Document review: <StatusBadge kind="document" value={fdr.document_status} /></div>
                <div className="text-sm">Bank verification: <StatusBadge kind="bank" value={fdr.bank_status} /></div>
              </div>
              {fdr.bank_verifications[0] && (
                <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-xs text-slate-700">
                  <SimulatedTag /> <span className="ml-1">Latest: {fdr.bank_verifications[0].outcome} · ref {fdr.bank_verifications[0].reference} · {fdr.bank_verifications[0].officer} · {fmtDateTime(fdr.bank_verifications[0].created_at)}</span>
                  <div className="mt-1">{fdr.bank_verifications[0].remarks}</div>
                </div>
              )}
              <DocumentList docs={fdr.documents} required={fdr.required_documents} />
              <div className="mt-4"><ValidationList items={fdr.validation_results} compact /></div>
            </Card>
          )}
          {fdr && <Card title="Complete audit trail"><AuditTimeline entries={fdr.audit} /></Card>}
        </div>

        <div className="space-y-6">
          <Card title="Prerequisites (current)">
            <ul className="space-y-2">
              {prereq.map((c) => (
                <li key={c.code} className="flex items-center gap-2 text-sm">
                  {c.ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Circle className="h-4 w-4 text-red-400" />}{c.label}
                </li>
              ))}
            </ul>
          </Card>

          <Card title={["approved", "rejected"].includes(cr.status) ? "Outcome" : isSenior && awaitingDecision ? "Final decision" : "Officer recommendation"}>
            {canDecide || canRecommend ? (
              <div className="space-y-3">
                {isSenior && canRecommend && <Alert tone="info">You are acting as the reviewing officer. A different senior officer must make the final decision.</Alert>}
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => setChoice("approve")} className={`btn border-2 ${choice === "approve" ? "border-emerald-500 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-white text-slate-600"}`}>
                    <ThumbsUp className="h-4 w-4" />{canDecide ? "Approve" : "Recommend approval"}
                  </button>
                  <button onClick={() => setChoice("reject")} className={`btn border-2 ${choice === "reject" ? "border-red-500 bg-red-50 text-red-800" : "border-slate-200 bg-white text-slate-600"}`}>
                    <ThumbsDown className="h-4 w-4" />{canDecide ? "Reject" : "Recommend rejection"}
                  </button>
                </div>
                <Field label={`Remarks (mandatory, min ${minLen} characters)`}>
                  <textarea className="input min-h-[110px]" value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder={canDecide ? "Record the basis for your decision…" : "Summarise the evidence reviewed…"} />
                </Field>
                <button className="btn-primary w-full" disabled={!choice || busy || remarks.trim().length < minLen} onClick={submit}>
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gavel className="h-4 w-4" />}{canDecide ? "Record final decision" : "Submit recommendation"}
                </button>
                {canDecide && <p className="text-xs text-slate-500">This records a demonstration approval only. It does not transfer or release bank funds.</p>}
              </div>
            ) : isSenior && awaitingDecision && selfRecommended ? (
              <Alert tone="error" title="Two-person rule">You recommended this request, so a different senior approving officer must make the final decision.</Alert>
            ) : cr.status === "approved" ? (
              <div className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="h-5 w-5" />Approved (demo workflow). No funds are released by this system.</div>
            ) : cr.status === "rejected" ? (
              <div className="flex items-center gap-2 text-sm text-red-700"><XCircle className="h-5 w-5" />Clearance rejected.</div>
            ) : awaitingDecision ? (
              <div className="flex items-center gap-2 text-sm text-slate-600"><ShieldAlert className="h-5 w-5 text-violet-600" />Recommendation submitted. Awaiting a senior approving officer.</div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-slate-600"><Ban className="h-5 w-5" />No action available for your role.</div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
