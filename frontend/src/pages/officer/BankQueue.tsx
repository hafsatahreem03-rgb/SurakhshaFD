import { useState } from "react";
import { Link } from "react-router-dom";
import { Landmark } from "lucide-react";
import { useFetch } from "../../lib/useFetch";
import { fmtDate, inr } from "../../lib/format";
import type { FDR, FDRDetail } from "../../lib/types";
import { BankSimulator } from "../../components/actions";
import { Alert, Card, EmptyState, ErrorState, Modal, PageHeader, Spinner, StatusBadge, Table } from "../../components/ui";

const FILTERS = [
  { key: "", label: "Needs verification" },
  { key: "pending", label: "Pending" },
  { key: "mismatch", label: "Mismatch" },
  { key: "failed", label: "Failed" },
  { key: "confirmed", label: "Confirmed" },
];

export default function BankQueue() {
  const [filter, setFilter] = useState("");
  const { data, loading, error, reload } = useFetch<FDR[]>("/fdrs", filter ? { bank_status: filter } : {});
  const [selected, setSelected] = useState<number | null>(null);
  const { data: detail, reload: reloadDetail } = useFetch<FDRDetail>(selected ? `/fdrs/${selected}` : null);

  const rows = (data || []).filter((f) => !f.is_cleared && f.submission_status === "submitted" && (filter || ["not_started", "pending", "mismatch", "failed"].includes(f.bank_status)));

  return (
    <div>
      <PageHeader title="Bank Verification Simulator" subtitle="Record simulated bank confirmations for submitted FDRs" />
      <div className="mb-4">
        <Alert tone="warning" title="Demo / Simulated">
          No bank is contacted in this prototype. Each outcome is chosen by the officer and is labelled as simulated everywhere. It is never genuine bank evidence.
        </Alert>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button key={f.key} onClick={() => setFilter(f.key)} className={`rounded-full px-3 py-1 text-sm font-medium ${filter === f.key ? "bg-navy-800 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{f.label}</button>
        ))}
      </div>
      <Card bodyClass="p-0">
        {loading ? <Spinner /> : error ? <div className="p-5"><ErrorState message={error} onRetry={reload} /></div> : rows.length ? (
          <Table head={["Reference", "Institution", "FDR / Bank", "Principal", "Maturity", "Documents", "Bank status", ""]}>
            {rows.map((f) => (
              <tr key={f.id} className="hover:bg-slate-50/70">
                <td className="td"><Link className="font-semibold text-navy-700 hover:underline" to={`/officer/cases/${f.id}?tab=bank`}>{f.reference_no}</Link></td>
                <td className="td max-w-[180px] truncate">{f.institution_name}</td>
                <td className="td"><div className="font-mono text-xs">{f.fdr_number}</div><div className="text-xs text-slate-500">{f.bank_name}</div></td>
                <td className="td font-semibold">{inr(f.principal_amount)}</td>
                <td className="td">{fmtDate(f.maturity_date)}</td>
                <td className="td"><StatusBadge kind="document" value={f.document_status} /></td>
                <td className="td"><StatusBadge kind="bank" value={f.bank_status} /></td>
                <td className="td text-right"><button className="btn-primary btn-sm" onClick={() => setSelected(f.id)}><Landmark className="h-3.5 w-3.5" />Simulate</button></td>
              </tr>
            ))}
          </Table>
        ) : <EmptyState title="Nothing in this queue" />}
      </Card>
      <Modal open={!!selected} wide title={detail ? `Simulate verification · ${detail.reference_no} · ${detail.fdr_number}` : "Loading…"} onClose={() => setSelected(null)}>
        {detail && detail.id === selected ? (
          <BankSimulator fdr={detail} onDone={() => { reloadDetail(); reload(); setSelected(null); }} />
        ) : <Spinner />}
      </Modal>
    </div>
  );
}
