import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, FileUp, Landmark, Loader2, RotateCcw, Undo2, XCircle } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import type { FDRDetail } from "../lib/types";
import { Alert, Field, Modal, SimulatedTag, useToast } from "./ui";

const REVIEW_ACTIONS = [
  { action: "mark_checked", label: "Mark documents checked", icon: CheckCircle2, cls: "btn-teal", hint: "Documents and entered details are consistent." },
  { action: "mark_discrepancy", label: "Mark discrepancy", icon: AlertTriangle, cls: "btn-outline", hint: "Flag an inconsistency that needs follow-up." },
  { action: "request_correction", label: "Request correction", icon: Undo2, cls: "btn-outline", hint: "Send back to the institution to fix and resubmit." },
  { action: "reject", label: "Reject document", icon: XCircle, cls: "btn-danger", hint: "The submitted document is not acceptable." },
] as const;

export function ReviewActions({ fdr, onDone }: { fdr: FDRDetail; onDone: () => void }) {
  const toast = useToast();
  const [pending, setPending] = useState<string | null>(null);
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy] = useState(false);
  const open = fdr.submission_status === "submitted" && ["pending_review", "discrepancy"].includes(fdr.document_status) && !fdr.is_cleared;
  const reopenable = fdr.submission_status === "submitted" && ["document_checked", "rejected"].includes(fdr.document_status) && !fdr.is_cleared;

  const run = async () => {
    setBusy(true);
    try {
      await api.post(`/fdrs/${fdr.id}/review`, { action: pending, remarks });
      toast("success", "Review recorded and the institution has been notified.");
      setPending(null);
      setRemarks("");
      onDone();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const current = REVIEW_ACTIONS.find((a) => a.action === pending) || (pending === "reopen" ? { label: "Reopen review", hint: "Move the case back to pending review." } : null);

  return (
    <div>
      {open ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {REVIEW_ACTIONS.map((a) => (
            <button key={a.action} className={`${a.cls} justify-start`} onClick={() => setPending(a.action)}>
              <a.icon className="h-4 w-4" />{a.label}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
          {fdr.submission_status === "correction_requested" ? "Waiting for the institution to correct and resubmit." : `Document review is closed (${fdr.document_status.replace(/_/g, " ")}).`}
          {reopenable && <button className="btn-outline btn-sm" onClick={() => setPending("reopen")}><RotateCcw className="h-3.5 w-3.5" />Reopen review</button>}
        </div>
      )}
      <Modal open={!!pending} title={current?.label || ""} onClose={() => setPending(null)}
        footer={<>
          <button className="btn-outline" onClick={() => setPending(null)}>Cancel</button>
          <button className="btn-primary" disabled={busy || remarks.trim().length < 3} onClick={run}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Confirm</button>
        </>}>
        <p className="mb-3 text-sm text-slate-600">{current?.hint}</p>
        <Field label="Review remarks (required, shared with the institution)">
          <textarea className="input min-h-[100px]" value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="e.g. Amount on the receipt matches the entered value; payment proof verified." />
        </Field>
      </Modal>
    </div>
  );
}

const OUTCOMES = [
  { value: "confirmed", label: "Bank confirmation received", icon: CheckCircle2, cls: "border-emerald-300 bg-emerald-50 text-emerald-800" },
  { value: "mismatch", label: "FDR details mismatch", icon: AlertTriangle, cls: "border-red-300 bg-red-50 text-red-800" },
  { value: "pending", label: "Verification pending", icon: Clock, cls: "border-amber-300 bg-amber-50 text-amber-800" },
  { value: "failed", label: "Verification failed", icon: XCircle, cls: "border-red-300 bg-red-50 text-red-800" },
];

export function BankSimulator({ fdr, onDone }: { fdr: FDRDetail; onDone: () => void }) {
  const toast = useToast();
  const [outcome, setOutcome] = useState("confirmed");
  const [remarks, setRemarks] = useState("");
  const [evidence, setEvidence] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const evidenceDocs = fdr.documents.filter((d) => d.doc_type === "bank_evidence");
  const blocked = fdr.submission_status === "draft" || fdr.is_cleared;

  const uploadEvidence = async (file: File) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", "bank_evidence");
      const r = await api.post(`/fdrs/${fdr.id}/documents`, fd);
      setEvidence(r.data.document.id);
      toast("success", "Evidence attached.");
      onDone();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/fdrs/${fdr.id}/bank-verifications`, { outcome, remarks, evidence_document_id: evidence || null });
      toast("success", `Simulated outcome "${outcome}" recorded (ref ${r.data.reference}).`);
      setRemarks("");
      onDone();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Alert tone="warning" title="Simulated bank verification">
        This prototype does not contact any bank. The officer chooses the outcome to demonstrate the workflow. Genuine verification requires confirmation obtained independently from the issuing bank. The backend uses an adapter interface so a real bank API can be plugged in later.
      </Alert>
      {blocked ? <div className="text-sm text-slate-500">Verification is not available for this record.</div> : (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            {OUTCOMES.map((o) => (
              <button key={o.value} type="button" onClick={() => setOutcome(o.value)}
                className={`flex items-center gap-2 rounded-lg border-2 px-3 py-2.5 text-left text-sm font-medium transition ${outcome === o.value ? o.cls : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"}`}>
                <o.icon className="h-4 w-4" />{o.label}
              </button>
            ))}
          </div>
          <Field label="Remarks (required)">
            <textarea className="input min-h-[80px]" value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="e.g. Branch manager confirmed FDR status by phone (demo simulation)." />
          </Field>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Supporting evidence (optional)">
              <select className="input" value={evidence} onChange={(e) => setEvidence(e.target.value ? Number(e.target.value) : "")}>
                <option value="">None</option>
                {evidenceDocs.map((d) => <option key={d.id} value={d.id}>{d.original_filename}</option>)}
              </select>
            </Field>
            <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadEvidence(f); e.target.value = ""; }} />
            <button className="btn-outline" disabled={busy} onClick={() => fileRef.current?.click()}><FileUp className="h-4 w-4" />Attach evidence</button>
          </div>
          <button className="btn-primary w-full" disabled={busy || remarks.trim().length < 3} onClick={submit}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Landmark className="h-4 w-4" />}Record simulated outcome <SimulatedTag className="ml-1 border-amber-300" />
          </button>
        </>
      )}
    </div>
  );
}
