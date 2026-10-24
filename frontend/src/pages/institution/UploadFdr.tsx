import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle, CheckCircle2, Download, FileSearch, FileUp, Loader2, Save, ScanLine, Send, ShieldCheck, Sparkles, UploadCloud,
} from "lucide-react";
import { api, downloadFile, errorMessage } from "../../lib/api";
import { useFetch } from "../../lib/useFetch";
import { DOC_TYPES, inr } from "../../lib/format";
import type { DocumentInfo, ExtractedField, FDRDetail, ValidationItem } from "../../lib/types";
import { DocumentList, DocumentPreview, ValidationList } from "../../components/fdr";
import { Alert, Badge, Card, ErrorState, PageHeader, Spinner, useToast } from "../../components/ui";

type Form = Record<FormKey, string>;
type FormKey = "fdr_number" | "bank_name" | "branch_name" | "account_holder" | "account_number_masked" | "principal_amount" | "interest_rate" | "issue_date" | "maturity_date";

const FIELDS: { key: FormKey; label: string; type?: string; placeholder?: string }[] = [
  { key: "bank_name", label: "Bank name" },
  { key: "branch_name", label: "Branch name" },
  { key: "fdr_number", label: "FDR number", placeholder: "e.g. SDCB/FDR/2026/004817" },
  { key: "account_holder", label: "Account holder" },
  { key: "principal_amount", label: "Principal amount (₹)", type: "number" },
  { key: "interest_rate", label: "Interest rate (% p.a.)", type: "number" },
  { key: "issue_date", label: "Issue date", type: "date" },
  { key: "maturity_date", label: "Maturity date", type: "date" },
  { key: "account_number_masked", label: "Account number (only last 4 digits are stored)", placeholder: "XXXXXX1234" },
];
const EMPTY: Form = Object.fromEntries(FIELDS.map((f) => [f.key, ""])) as Form;

/** Normalise a value so the entered form value can be compared with the raw OCR value. */
function norm(key: string, v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "";
  if (key === "principal_amount" || key === "interest_rate") {
    const n = Number(String(v).replace(/,/g, ""));
    return isNaN(n) ? String(v) : n.toFixed(2);
  }
  return String(v).trim();
}

function ConfidenceBadge({ f }: { f: ExtractedField | undefined }) {
  if (!f) return null;
  if (!f.extracted_value) return <Badge tone="amber">Not found · enter manually</Badge>;
  if (f.needs_review) return <Badge tone="amber">Needs review · {f.confidence ?? "?"}%</Badge>;
  return <Badge tone="green">OCR {f.confidence}%</Badge>;
}

export default function UploadFdr() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const fdrId = id ? Number(id) : null;
  const { data: fdr, loading, error, reload } = useFetch<FDRDetail>(fdrId ? `/fdrs/${fdrId}` : null);
  const { data: samples } = useFetch<{ name: string; size_bytes: number }[]>("/samples");
  const [form, setForm] = useState<Form>(EMPTY);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<ValidationItem[] | null>(null);
  const [supportType, setSupportType] = useState("payment_proof");
  const fileRef = useRef<HTMLInputElement>(null);
  const supportRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  // Load saved values into the form when the record loads
  useEffect(() => {
    if (!fdr) return;
    setForm((cur) => {
      const next = { ...cur };
      const ocrNow = Object.fromEntries(fdr.extracted_fields.map((f) => [f.field_name, f.extracted_value]));
      FIELDS.forEach(({ key }) => {
        const v = (fdr as any)[key];
        if (v !== null && v !== undefined && v !== "") next[key] = String(v);
        else if (!next[key] && ocrNow[key]) next[key] = ocrNow[key]!; // pre-fill from OCR for the user to confirm
      });
      return next;
    });
    if (fdr.validation_results.length && !results) setResults(fdr.validation_results);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fdr?.id, fdr?.updated_at, fdr?.receipt_document_id]);

  const ocr = useMemo(() => Object.fromEntries((fdr?.extracted_fields || []).map((f) => [f.field_name, f])) as Record<string, ExtractedField>, [fdr]);
  const receipt: DocumentInfo | undefined = fdr?.documents.filter((d) => d.doc_type === "fdr_receipt").slice(-1)[0];
  const editable = !fdr || ["draft", "correction_requested"].includes(fdr.submission_status);

  /** Any edit makes earlier validation results stale, so they are cleared until checks run again. */
  const edit = (key: FormKey, value: string) => {
    setForm((cur) => ({ ...cur, [key]: value }));
    setResults(null);
  };

  const mismatch = (key: FormKey) => {
    const o = ocr[key]?.extracted_value;
    return !!(o && form[key] && norm(key, o) !== norm(key, form[key]));
  };
  const amountMismatch = mismatch("principal_amount");

  const ensureFdr = async (): Promise<number> => {
    if (fdrId) return fdrId;
    const r = await api.post("/fdrs", {});
    return r.data.id;
  };

  const uploadReceipt = async (file: File) => {
    setOcrBusy(true);
    setResults(null);
    try {
      const fid = await ensureFdr();
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", "fdr_receipt");
      const r = await api.post(`/fdrs/${fid}/documents`, fd);
      const fields: ExtractedField[] = r.data.extracted_fields;
      // Pre-fill only empty fields; the institution confirms or edits every value.
      setForm((cur) => {
        const next = { ...cur };
        fields.forEach((f) => {
          if (f.field_name in next && f.extracted_value && !next[f.field_name as FormKey]) next[f.field_name as FormKey] = f.extracted_value;
        });
        return next;
      });
      const doc = r.data.document as DocumentInfo;
      if (doc.ocr_status === "completed") toast("success", `OCR complete in ${((doc.ocr_duration_ms || 0) / 1000).toFixed(1)}s: ${doc.ocr_message}`);
      else toast("error", doc.ocr_message || "OCR could not read this document. Please enter details manually.");
      if (fdrId) reload();
      else navigate(`/institution/upload/${fid}`, { replace: true }); // the new draft now has an id
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setOcrBusy(false);
    }
  };

  const uploadSupport = async (file: File) => {
    if (!fdrId) return;
    setBusy("support");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", supportType);
      await api.post(`/fdrs/${fdrId}/documents`, fd);
      toast("success", `${DOC_TYPES[supportType]} uploaded.`);
      reload();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(null);
      if (supportRef.current) supportRef.current.value = "";
    }
  };

  const save = async (fid: number) => {
    const body: Record<string, unknown> = {};
    FIELDS.forEach(({ key, type }) => {
      const v = form[key].trim();
      body[key] = v === "" ? null : type === "number" ? Number(v) : v;
    });
    await api.put(`/fdrs/${fid}`, body);
    const confirmations = (fdr?.extracted_fields || []).map((f) => ({
      id: f.id,
      confirmed_value: f.field_name in form ? norm(f.field_name, form[f.field_name as FormKey]) || null : f.extracted_value,
    }));
    if (confirmations.length) await api.put(`/fdrs/${fid}/extracted-fields`, { fields: confirmations });
  };

  const act = async (kind: "save" | "validate" | "submit") => {
    if (!fdrId) return;
    setBusy(kind);
    try {
      await save(fdrId);
      if (kind === "save") {
        toast("success", "Draft saved.");
        reload();
      } else if (kind === "validate") {
        const r = await api.post(`/fdrs/${fdrId}/validate`);
        setResults(r.data.results);
        const s = r.data.summary;
        toast(s.errors ? "error" : "info", `Validation: ${s.errors} error(s), ${s.warnings} warning(s), ${s.passed} passed.`);
        reload();
      } else {
        try {
          const r = await api.post(`/fdrs/${fdrId}/submit`);
          toast("success", `${r.data.fdr.reference_no} submitted for AICTE review.`);
          navigate(`/institution/fdrs/${fdrId}`);
        } catch (e: any) {
          if (e.response?.status === 422 && e.response.data?.detail?.results) {
            setResults(e.response.data.detail.results);
            toast("error", "Please fix the highlighted errors before submitting.");
          } else throw e;
        }
      }
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  if (fdrId && loading && !fdr) return <Spinner />;
  if (fdrId && error) return <ErrorState message={error} onRetry={reload} />;
  if (fdr && !editable) {
    return (
      <Card>
        <Alert tone="info" title={`${fdr.reference_no} has already been submitted`}>
          It can be edited again only if an officer requests a correction. <Link className="font-semibold underline" to={`/institution/fdrs/${fdr.id}`}>Open FDR details</Link>
        </Alert>
      </Card>
    );
  }

  return (
    <div>
      <PageHeader title={fdr ? `${fdr.submission_status === "correction_requested" ? "Correct" : "Complete"} ${fdr.reference_no}` : "Upload FDR"}
        subtitle="Step 1: upload the FDR receipt. Step 2: review the OCR reading. Step 3: add supporting documents and submit." />

      {fdr?.submission_status === "correction_requested" && (
        <div className="mb-4"><Alert tone="warning" title="Correction requested by AICTE officer">{fdr.last_review_remarks}</Alert></div>
      )}

      {/* Step 1 */}
      <Card title={<span className="flex items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-800 text-xs text-white">1</span>FDR receipt</span>}
        subtitle="PDF, JPG or PNG up to 10 MB. Tesseract OCR runs on the server as soon as the file is uploaded."
        action={samples?.length ? (
          <div className="flex flex-wrap gap-2">
            {samples.filter((s) => s.name.includes("FDR") || s.name.includes("Payment")).map((s) => (
              <button key={s.name} className="btn-outline btn-sm" onClick={() => downloadFile(`/samples/${s.name}`, s.name)} title="Fictional sample document">
                <Download className="h-3.5 w-3.5" />{s.name.replace("SAMPLE_", "").replace(/_/g, " ")}
              </button>
            ))}
          </div>
        ) : undefined}>
        <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadReceipt(f); e.target.value = ""; }} />
        <button type="button" disabled={ocrBusy}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) uploadReceipt(f); }}
          className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${drag ? "border-teal-500 bg-teal-50" : "border-slate-300 bg-slate-50 hover:border-teal-400 hover:bg-teal-50/40"}`}>
          {ocrBusy ? (
            <>
              <ScanLine className="h-9 w-9 animate-pulse text-teal-600" />
              <div className="font-semibold text-navy-900">Running Tesseract OCR…</div>
              <div className="text-sm text-slate-500">Rendering pages, reading text and locating FDR fields</div>
            </>
          ) : (
            <>
              <UploadCloud className="h-9 w-9 text-teal-600" />
              <div className="font-semibold text-navy-900">{receipt ? "Upload a different FDR receipt" : "Drop the FDR receipt here or click to choose"}</div>
              <div className="text-sm text-slate-500">{receipt ? `Current: ${receipt.original_filename}` : "Use the sample buttons above to download a fictional test FDR"}</div>
            </>
          )}
        </button>
      </Card>

      {fdr && receipt && (
        <>
          {/* Step 2 */}
          <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.1fr]">
            <Card title="Original document" subtitle={receipt.original_filename} bodyClass="p-3">
              <DocumentPreview doc={receipt} className="h-[720px]" />
            </Card>
            <Card title={<span className="flex items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-800 text-xs text-white">2</span>Review OCR results and deposit details</span>}
              subtitle={receipt.ocr_status === "completed"
                ? <span className="flex flex-wrap items-center gap-1"><Sparkles className="h-3 w-3 text-teal-600" />{receipt.ocr_engine} · mean confidence {receipt.ocr_mean_confidence}% · {receipt.ocr_message}</span>
                : receipt.ocr_message || "OCR not available - enter values manually"}>
              {ocr.institution_name?.extracted_value && (
                <div className="mb-4 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Institution on document: </span>
                  {ocr.institution_name.extracted_value} <ConfidenceBadge f={ocr.institution_name} />
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                {FIELDS.map(({ key, label, type, placeholder }) => {
                  const f = ocr[key];
                  const bad = mismatch(key);
                  return (
                    <div key={key} className={key === "account_number_masked" ? "sm:col-span-2" : ""}>
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="label mb-0">{label}</span>
                        {key !== "account_number_masked" && <ConfidenceBadge f={f} />}
                      </div>
                      <input className={`input ${bad ? "border-red-400 bg-red-50 ring-2 ring-red-200" : f?.needs_review && f.extracted_value ? "border-amber-300" : ""}`}
                        type={type || "text"} step={type === "number" ? "any" : undefined} placeholder={placeholder}
                        value={form[key]} onChange={(e) => edit(key, e.target.value)} />
                      {bad && (
                        <div className="mt-1 text-xs text-red-600">
                          Document reads <b>{key === "principal_amount" ? inr(Number(f!.extracted_value)) : f!.extracted_value}</b>
                          <button className="ml-2 font-semibold underline" onClick={() => edit(key, f!.extracted_value!)}>Use document value</button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {amountMismatch && (
                <div className="mt-4"><Alert tone="error" title="Amount mismatch detected">
                  You entered {inr(Number(form.principal_amount))} but the uploaded FDR reads {inr(Number(ocr.principal_amount.extracted_value))}. Please review the uploaded FDR and entered information.
                </Alert></div>
              )}
              <p className="mt-4 flex items-start gap-2 text-xs text-slate-500">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 flex-none text-teal-600" />
                The raw OCR reading is kept unchanged for the officer. Your confirmed or corrected values are stored alongside it, and every correction is recorded in the audit trail.
              </p>
            </Card>
          </div>

          {/* Step 3 */}
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card title={<span className="flex items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-800 text-xs text-white">3</span>Supporting documents</span>}
              subtitle="Required documents are set by the (demo) policy">
              <DocumentList docs={fdr.documents} required={fdr.required_documents} />
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <select className="input w-auto" value={supportType} onChange={(e) => setSupportType(e.target.value)}>
                  {["payment_proof", "lien_letter", "other"].map((t) => <option key={t} value={t}>{DOC_TYPES[t]}</option>)}
                </select>
                <input ref={supportRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadSupport(f); }} />
                <button className="btn-outline" disabled={busy === "support"} onClick={() => supportRef.current?.click()}>
                  {busy === "support" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}Upload {DOC_TYPES[supportType].toLowerCase()}
                </button>
              </div>
            </Card>
            <Card title="Automatic validation" subtitle="Errors block submission. Warnings are flagged for the officer and never cause automatic rejection."
              action={<button className="btn-outline btn-sm" disabled={!!busy} onClick={() => act("validate")}>{busy === "validate" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileSearch className="h-3.5 w-3.5" />}Run checks</button>}>
              {results ? <ValidationList items={results} compact /> : <div className="text-sm text-slate-500">Click <b>Run checks</b> to validate the current details before submitting.</div>}
            </Card>
          </div>

          <div className="sticky bottom-0 z-10 -mx-4 mt-6 flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:-mx-8 lg:px-8">
            {amountMismatch && <span className="mr-auto flex items-center gap-1 text-sm text-red-600"><AlertTriangle className="h-4 w-4" />Amount mismatch with document</span>}
            {!amountMismatch && results && !results.some((r) => r.severity === "error") && <span className="mr-auto flex items-center gap-1 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" />Ready to submit</span>}
            <button className="btn-outline" disabled={!!busy} onClick={() => act("save")}>{busy === "save" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Save draft</button>
            <button className="btn-teal" disabled={!!busy} onClick={() => act("submit")}>{busy === "submit" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{fdr.submission_status === "correction_requested" ? "Resubmit for review" : "Submit for review"}</button>
          </div>
        </>
      )}
    </div>
  );
}
