import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, Ban, Building, CheckCircle2, Circle, Clock, Download, Eye, FileSearch, FileText, Info, Landmark,
  Loader2, ScrollText, Send, Stamp, Upload, User as UserIcon, XCircle,
} from "lucide-react";
import { downloadFile, errorMessage, fetchBlobUrl } from "../lib/api";
import { DOC_TYPES, fmtDate, fmtDateTime, humanize, inr } from "../lib/format";
import type { AuditEntry, DocumentInfo, FDR, FDRDetail, ValidationItem } from "../lib/types";
import { Badge, EmptyState, Modal, SimulatedTag, StatusBadge, Table } from "./ui";

export function MaturityBadge({ days, cleared }: { days: number | null; cleared?: boolean }) {
  if (days === null || cleared) return null;
  if (days < 0) return <Badge tone="red">Matured {Math.abs(days)}d ago</Badge>;
  if (days <= 7) return <Badge tone="red">{days}d to maturity</Badge>;
  if (days <= 30) return <Badge tone="amber">{days}d to maturity</Badge>;
  if (days <= 60) return <Badge tone="blue">{days}d to maturity</Badge>;
  return null;
}

export function FdrTable({ rows, linkTo, showInstitution = true, empty }: {
  rows: FDR[]; linkTo: (f: FDR) => string; showInstitution?: boolean; empty?: React.ReactNode;
}) {
  if (!rows.length) return <>{empty || <EmptyState title="No FDR records found" message="Try changing the filters." />}</>;
  return (
    <Table head={["Reference", ...(showInstitution ? ["Institution"] : []), "FDR / Bank", "Principal", "Maturity", "Documents", "Bank (sim)", "Stage", ""]}>
      {rows.map((f) => (
        <tr key={f.id} className="transition hover:bg-slate-50/70">
          <td className="td">
            <Link to={linkTo(f)} className="font-semibold text-navy-700 hover:underline">{f.reference_no}</Link>
            {f.validation && (f.validation.warnings > 0 || f.validation.errors > 0) && (
              <div className="mt-0.5 flex items-center gap-1 text-xs text-amber-700"><AlertTriangle className="h-3 w-3" />{f.validation.errors + f.validation.warnings} issue(s)</div>
            )}
          </td>
          {showInstitution && <td className="td max-w-[200px] truncate text-slate-600">{f.institution_name}</td>}
          <td className="td">
            <div className="font-mono text-xs text-slate-700">{f.fdr_number || <span className="italic text-slate-400">not entered</span>}</div>
            <div className="text-xs text-slate-500">{f.bank_name || "—"}</div>
          </td>
          <td className="td font-semibold tabular-nums">{inr(f.principal_amount)}</td>
          <td className="td">
            <div className="text-slate-700">{fmtDate(f.maturity_date)}</div>
            <MaturityBadge days={f.days_to_maturity} cleared={f.is_cleared} />
          </td>
          <td className="td"><StatusBadge kind="document" value={f.document_status} /></td>
          <td className="td"><StatusBadge kind="bank" value={f.bank_status} /></td>
          <td className="td"><StatusBadge kind="stage" value={f.stage} /></td>
          <td className="td text-right"><Link to={linkTo(f)} className="btn-outline btn-sm">Open</Link></td>
        </tr>
      ))}
    </Table>
  );
}

/** Five separate stages - submission, document review, bank verification, clearance decision, fund release. */
export function StatusTracker({ fdr }: { fdr: FDRDetail | FDR }) {
  const cr = "clearance_requests" in fdr ? fdr.clearance_requests[0] : null;
  const sub = fdr.submission_status === "submitted" ? "done" : fdr.submission_status === "correction_requested" ? "warn" : "todo";
  const doc = { document_checked: "done", discrepancy: "warn", correction_requested: "warn", rejected: "fail", pending_review: "active" }[fdr.document_status] || "todo";
  const bank = { confirmed: "done", pending: "active", mismatch: "fail", failed: "fail" }[fdr.bank_status] || "todo";
  const clear = fdr.is_cleared ? "done" : cr?.status === "rejected" ? "fail" : cr ? "active" : "todo";
  const steps = [
    { label: "Submission", sub: humanize(fdr.submission_status), state: sub, icon: Send },
    { label: "Document review", sub: humanize(fdr.document_status), state: doc, icon: FileSearch },
    { label: "Bank verification", sub: `${humanize(fdr.bank_status)} · simulated`, state: bank, icon: Landmark },
    { label: "Clearance decision", sub: cr ? humanize(cr.status) : fdr.clearance_status ? humanize(fdr.clearance_status) : "Not requested", state: clear, icon: Stamp },
    { label: "Actual fund release", sub: "Outside this system", state: "na", icon: Ban },
  ];
  const tone: Record<string, string> = {
    done: "bg-emerald-500 text-white", active: "bg-blue-500 text-white", warn: "bg-amber-500 text-white",
    fail: "bg-red-500 text-white", todo: "bg-slate-200 text-slate-500", na: "bg-slate-100 text-slate-400 border border-dashed border-slate-300",
  };
  return (
    <ol className="grid grid-cols-1 gap-3 sm:grid-cols-5">
      {steps.map((s, i) => (
        <li key={s.label} className="relative flex items-start gap-3 sm:flex-col sm:items-center sm:text-center">
          {i < steps.length - 1 && <span className="absolute left-[18px] top-9 hidden h-0.5 w-[calc(100%-36px)] translate-x-[36px] bg-slate-200 sm:block" />}
          <span className={`relative z-10 flex h-9 w-9 flex-none items-center justify-center rounded-full ${tone[s.state]}`}>
            {s.state === "done" ? <CheckCircle2 className="h-5 w-5" /> : s.state === "fail" ? <XCircle className="h-5 w-5" /> : <s.icon className="h-4 w-4" />}
          </span>
          <div>
            <div className="text-xs font-semibold text-navy-900">{s.label}</div>
            <div className="text-[11px] text-slate-500">{s.sub}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function ValidationList({ items, compact = false }: { items: ValidationItem[]; compact?: boolean }) {
  if (!items.length) return <div className="text-sm text-slate-500">Validation has not been run yet.</div>;
  const order = { error: 0, warning: 1, info: 2, pass: 3 };
  const sorted = [...items].sort((a, b) => order[a.severity] - order[b.severity]);
  const shown = compact ? sorted.filter((i) => i.severity !== "pass") : sorted;
  const cfg = {
    error: ["border-red-200 bg-red-50 text-red-800", XCircle, "Error · must fix"],
    warning: ["border-amber-200 bg-amber-50 text-amber-900", AlertTriangle, "Needs review"],
    info: ["border-blue-200 bg-blue-50 text-blue-800", Info, "Info"],
    pass: ["border-emerald-200 bg-emerald-50/60 text-emerald-800", CheckCircle2, "Passed"],
  } as const;
  return (
    <ul className="space-y-2">
      {shown.length === 0 && <li className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" /> All checks passed.</li>}
      {shown.map((v, i) => {
        const [cls, Icon, tag] = cfg[v.severity];
        return (
          <li key={i} className={`flex gap-2.5 rounded-lg border px-3 py-2 text-sm ${cls}`}>
            <Icon className="mt-0.5 h-4 w-4 flex-none" />
            <div className="min-w-0">
              <span className="mr-2 text-[10px] font-bold uppercase tracking-wider opacity-70">{tag} · {v.check_code.replace(/_/g, " ")}</span>
              <div>{v.message}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

const ACTION_ICON: Record<string, any> = {
  fdr_created: FileText, document_uploaded: Upload, ocr_completed: FileSearch, ocr_reviewed: CheckCircle2,
  validation_run: ScrollText, fdr_submitted: Send, fdr_resubmitted: Send, bank_verification_simulated: Landmark,
  clearance_requested: Stamp, clearance_recommended: Stamp, clearance_decided: Stamp, case_assigned: UserIcon,
  submission_blocked: XCircle, two_person_rule_blocked: Ban,
};

export function AuditTimeline({ entries }: { entries: AuditEntry[] }) {
  if (!entries.length) return <EmptyState title="No audit entries yet" />;
  return (
    <ol className="relative space-y-4 border-l-2 border-slate-200 pl-6">
      {entries.map((a) => {
        const Icon = ACTION_ICON[a.action] || (a.action.startsWith("review_") ? FileSearch : Clock);
        const bad = /blocked|reject|mismatch|failed/.test(a.action + (a.new_status || ""));
        return (
          <li key={a.id} className="relative">
            <span className={`absolute -left-[35px] flex h-7 w-7 items-center justify-center rounded-full ring-4 ring-white ${bad ? "bg-red-100 text-red-600" : "bg-teal-100 text-teal-700"}`}>
              <Icon className="h-3.5 w-3.5" />
            </span>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-sm font-semibold text-navy-900">{humanize(a.action)}</span>
              {a.action === "bank_verification_simulated" && <SimulatedTag />}
              <span className="text-xs text-slate-400">{fmtDateTime(a.created_at)}</span>
            </div>
            <div className="text-sm text-slate-600">{a.description}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>{a.user_email || "system"}{a.role ? ` · ${humanize(a.role)}` : ""}</span>
              {(a.previous_status || a.new_status) && (
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px]">{a.previous_status || "∅"} → {a.new_status || "∅"}</span>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Shows a protected document (PDF or image) fetched with the auth header. */
export function DocumentPreview({ doc, className = "h-[640px]" }: { doc: DocumentInfo | null | undefined; className?: string }) {
  const [src, setSrc] = useState<{ url: string; type: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!doc) return;
    let url = "";
    setSrc(null);
    setErr(null);
    fetchBlobUrl(`/documents/${doc.id}/file`)
      .then((r) => { url = r.url; setSrc(r); })
      .catch((e) => setErr(errorMessage(e)));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [doc?.id]);
  if (!doc) return <EmptyState title="No document uploaded" />;
  if (err) return <div className="p-4 text-sm text-red-600">{err}</div>;
  if (!src) return <div className={`flex items-center justify-center ${className}`}><Loader2 className="h-6 w-6 animate-spin text-teal-600" /></div>;
  return src.type.includes("pdf")
    ? <iframe title={doc.original_filename} src={src.url} className={`w-full rounded-lg border border-slate-200 bg-slate-100 ${className}`} />
    : <div className={`overflow-auto rounded-lg border border-slate-200 bg-slate-100 ${className}`}><img src={src.url} alt={doc.original_filename} className="w-full" /></div>;
}

export function DocumentList({ docs, required = [] }: { docs: DocumentInfo[]; required?: string[] }) {
  const [preview, setPreview] = useState<DocumentInfo | null>(null);
  const missing = required.filter((r) => !docs.some((d) => d.doc_type === r));
  return (
    <div className="space-y-2">
      {docs.map((d) => (
        <div key={d.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 px-3 py-2">
          <FileText className="h-5 w-5 text-navy-500" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{d.original_filename}</div>
            <div className="text-xs text-slate-500">
              {DOC_TYPES[d.doc_type] || d.doc_type} · {(d.size_bytes / 1024).toFixed(0)} KB · {fmtDateTime(d.uploaded_at)}
              {d.doc_type === "fdr_receipt" && d.ocr_status !== "not_run" && <> · OCR {d.ocr_status}{d.ocr_mean_confidence ? ` (${d.ocr_mean_confidence}%)` : ""}</>}
            </div>
          </div>
          {d.doc_type === "bank_evidence" && <SimulatedTag />}
          <button className="btn-outline btn-sm" onClick={() => setPreview(d)}><Eye className="h-3.5 w-3.5" />View</button>
          <button className="btn-outline btn-sm" onClick={() => downloadFile(`/documents/${d.id}/file`, d.original_filename)}><Download className="h-3.5 w-3.5" /></button>
        </div>
      ))}
      {missing.map((m) => (
        <div key={m} className="flex items-center gap-3 rounded-lg border border-dashed border-red-300 bg-red-50/50 px-3 py-2 text-sm text-red-700">
          <Circle className="h-4 w-4" /> Missing required document: {DOC_TYPES[m] || m}
        </div>
      ))}
      {!docs.length && !missing.length && <div className="text-sm text-slate-500">No documents.</div>}
      <Modal open={!!preview} title={preview?.original_filename || ""} onClose={() => setPreview(null)} wide>
        <DocumentPreview doc={preview} className="h-[70vh]" />
      </Modal>
    </div>
  );
}

export function FactGrid({ fdr }: { fdr: FDR }) {
  const facts: [string, React.ReactNode][] = [
    ["Institution", <span className="flex items-center gap-1"><Building className="h-3.5 w-3.5 text-slate-400" />{fdr.institution_name}</span>],
    ["FDR number", <span className="font-mono">{fdr.fdr_number || "—"}</span>],
    ["Bank (fictional)", fdr.bank_name || "—"],
    ["Branch", fdr.branch_name || "—"],
    ["Account holder", fdr.account_holder || "—"],
    ["Account no.", fdr.account_number_masked || "—"],
    ["Principal amount", <span className="font-semibold">{inr(fdr.principal_amount)}</span>],
    ["Interest rate", fdr.interest_rate != null ? `${fdr.interest_rate}% p.a.` : "—"],
    ["Issue date", fmtDate(fdr.issue_date)],
    ["Maturity date", <span className="flex flex-wrap items-center gap-2">{fmtDate(fdr.maturity_date)}<MaturityBadge days={fdr.days_to_maturity} cleared={fdr.is_cleared} /></span>],
    ["Submitted", fmtDateTime(fdr.submitted_at)],
    ["Assigned officer", fdr.assigned_officer || "Unassigned"],
  ];
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
      {facts.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{k}</dt>
          <dd className="mt-0.5 text-sm text-slate-800">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
