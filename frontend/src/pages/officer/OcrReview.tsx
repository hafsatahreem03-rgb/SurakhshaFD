import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown } from "lucide-react";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { inr } from "../../lib/format";
import type { FDRDetail } from "../../lib/types";
import { DocumentPreview, ValidationList } from "../../components/fdr";
import { ReviewActions } from "../../components/actions";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge, Table } from "../../components/ui";

function fmt(field: string, v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (field === "principal_amount") return inr(Number(v));
  return String(v);
}

function same(field: string, a: unknown, b: unknown): boolean {
  if (a == null || b == null || a === "" || b === "") return true; // nothing to compare
  if (field === "principal_amount" || field === "interest_rate") return Math.abs(Number(a) - Number(b)) < 1;
  return String(a).replace(/[^a-z0-9]/gi, "").toLowerCase() === String(b).replace(/[^a-z0-9]/gi, "").toLowerCase();
}

export default function OcrReview() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data: fdr, loading, error, reload } = useFetch<FDRDetail>(`/fdrs/${id}`);
  const [showText, setShowText] = useState(false);
  if (loading && !fdr) return <Spinner />;
  if (error || !fdr) return <ErrorState message={error || "Not found"} onRetry={reload} />;
  const receipt = fdr.documents.find((d) => d.id === fdr.receipt_document_id);
  // The OCR "institution name" is compared against the registered name without the "(Demo)" label.
  const submittedValue = (field: string) =>
    field === "institution_name" ? fdr.institution_name.replace(/\s*\(demo\)/i, "") : (fdr as any)[field];
  const mismatches = fdr.extracted_fields.filter((f) => f.field_name in fdr && !same(f.field_name, f.extracted_value, submittedValue(f.field_name)));

  return (
    <div>
      <Link to={`/${user!.role}/cases/${fdr.id}`} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-700"><ArrowLeft className="h-4 w-4" />Back to case</Link>
      <PageHeader title={`OCR Review · ${fdr.reference_no}`}
        subtitle={<span className="flex flex-wrap items-center gap-2">{fdr.institution_name} <StatusBadge kind="document" value={fdr.document_status} /></span>} />

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Uploaded FDR receipt" subtitle={receipt ? `${receipt.original_filename} · ${receipt.ocr_engine || "no OCR"}` : undefined} bodyClass="p-3">
          <DocumentPreview doc={receipt} className="h-[760px]" />
        </Card>
        <div className="space-y-6">
          <Card title="OCR reading vs submitted record" subtitle="Raw OCR values are never modified. Rows in red differ from what the institution submitted."
            bodyClass="p-0" action={mismatches.length ? <Badge tone="red">{mismatches.length} difference(s)</Badge> : <Badge tone="green">No differences</Badge>}>
            {fdr.extracted_fields.length ? (
              <Table head={["Field", "OCR value", "Confidence", "Institution confirmed", "Submitted record"]}>
                {fdr.extracted_fields.map((f) => {
                  const submitted = f.field_name in fdr ? submittedValue(f.field_name) : null;
                  const diff = f.field_name in fdr && !same(f.field_name, f.extracted_value, submitted);
                  return (
                    <tr key={f.id} className={diff ? "bg-red-50" : ""}>
                      <td className="td font-medium">
                        <span className="flex items-center gap-1">{diff && <AlertTriangle className="h-3.5 w-3.5 text-red-600" />}{f.label}</span>
                      </td>
                      <td className="td font-mono text-xs">{fmt(f.field_name, f.extracted_value)}</td>
                      <td className="td">
                        {f.confidence == null ? <Badge tone="gray">n/a</Badge> : <Badge tone={f.needs_review ? "amber" : "green"}>{f.confidence}%</Badge>}
                      </td>
                      <td className="td text-xs">
                        {f.is_confirmed ? (
                          <span className="flex items-center gap-1">{f.was_corrected ? <Badge tone="amber">corrected</Badge> : <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />}{fmt(f.field_name, f.confirmed_value)}</span>
                        ) : <span className="text-slate-400">not confirmed</span>}
                      </td>
                      <td className={`td text-xs ${diff ? "font-semibold text-red-700" : ""}`}>{f.field_name in fdr ? fmt(f.field_name, submitted) : "—"}</td>
                    </tr>
                  );
                })}
              </Table>
            ) : <EmptyState title="No OCR data" message="The receipt was not OCR-processed. Compare the document manually." />}
          </Card>
          <Card title="Validation findings"><ValidationList items={fdr.validation_results} compact /></Card>
          <Card title="Record your review"><ReviewActions fdr={fdr} onDone={reload} /></Card>
          <Card bodyClass="p-0">
            <button className="flex w-full items-center justify-between px-5 py-3 text-sm font-semibold text-navy-800" onClick={() => setShowText(!showText)}>
              Raw OCR text <ChevronDown className={`h-4 w-4 transition ${showText ? "rotate-180" : ""}`} />
            </button>
            {showText && <pre className="max-h-80 overflow-auto whitespace-pre-wrap border-t border-slate-100 bg-slate-50 p-4 font-mono text-xs text-slate-700">{fdr.ocr_text || "(no text)"}</pre>}
          </Card>
        </div>
      </div>
    </div>
  );
}
