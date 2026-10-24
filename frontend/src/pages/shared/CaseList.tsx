import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Download, FileUp, RotateCcw, Search } from "lucide-react";
import { downloadFile } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { BANK_STATUS, DOC_STATUS, STAGES, caseLink } from "../../lib/format";
import type { FDR } from "../../lib/types";
import { FdrTable } from "../../components/fdr";
import { Card, EmptyState, ErrorState, PageHeader, Spinner } from "../../components/ui";

const KEYS = ["q", "stage", "document_status", "bank_status", "institution_id", "assigned", "maturing_within_days", "date_from", "date_to"];

export default function CaseList() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const initial = Object.fromEntries(KEYS.map((k) => [k, params.get(k) || ""]));
  const [filters, setFilters] = useState<Record<string, string>>(initial);
  const [q, setQ] = useState(initial.q);
  const isInst = user?.role === "institution";
  const { data, loading, error, reload } = useFetch<FDR[]>("/fdrs", filters);
  const { data: institutions } = useFetch<{ id: number; name: string }[]>(isInst ? null : "/institutions");

  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q })), 300);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    setParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), { replace: true });
  }, [filters, setParams]);

  const set = (k: string, v: string) => setFilters((f) => ({ ...f, [k]: v }));
  const reset = () => { setQ(""); setFilters(Object.fromEntries(KEYS.map((k) => [k, ""]))); };
  const title = isInst ? "My FDRs" : user?.role === "officer" ? "All / Pending Cases" : "All Cases";

  return (
    <div>
      <PageHeader title={title}
        subtitle={isInst ? "Every FDR and security deposit your institution has filed" : "Submitted FDR cases across institutions (drafts are private to institutions)"}
        actions={<>
          <button className="btn-outline" onClick={() => downloadFile("/reports/fdrs.csv", "surakshafd-fdrs.csv", Object.fromEntries(Object.entries(filters).filter(([k, v]) => v && ["institution_id", "stage", "date_from", "date_to"].includes(k))))}>
            <Download className="h-4 w-4" />Export CSV
          </button>
          {isInst && <Link to="/institution/upload" className="btn-teal"><FileUp className="h-4 w-4" />Upload FDR</Link>}
        </>} />

      <Card className="mb-4" bodyClass="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative sm:col-span-2">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input className="input pl-9" placeholder="Search reference, FDR number, bank or holder…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <select className="input" value={filters.stage} onChange={(e) => set("stage", e.target.value)}>
            <option value="">All stages</option>
            {Object.entries(STAGES).filter(([k]) => !isInst ? k !== "draft" : true).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <select className="input" value={filters.document_status} onChange={(e) => set("document_status", e.target.value)}>
            <option value="">Any document status</option>
            {Object.entries(DOC_STATUS).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <select className="input" value={filters.bank_status} onChange={(e) => set("bank_status", e.target.value)}>
            <option value="">Any bank status (simulated)</option>
            {Object.entries(BANK_STATUS).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
          </select>
          {!isInst && (
            <select className="input" value={filters.institution_id} onChange={(e) => set("institution_id", e.target.value)}>
              <option value="">All institutions</option>
              {institutions?.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
            </select>
          )}
          <select className="input" value={filters.maturing_within_days} onChange={(e) => set("maturing_within_days", e.target.value)}>
            <option value="">Any maturity</option>
            <option value="7">Matured or ≤ 7 days</option>
            <option value="30">Matured or ≤ 30 days</option>
            <option value="60">Matured or ≤ 60 days</option>
          </select>
          {user?.role === "officer" && (
            <select className="input" value={filters.assigned} onChange={(e) => set("assigned", e.target.value)}>
              <option value="">Any assignment</option>
              <option value="me">Assigned to me</option>
              <option value="unassigned">Unassigned</option>
            </select>
          )}
          <div className="flex gap-2">
            <input type="date" className="input" title="Created from" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} />
            <input type="date" className="input" title="Created to" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} />
          </div>
          <button className="btn-outline" onClick={reset}><RotateCcw className="h-4 w-4" />Reset filters</button>
        </div>
      </Card>

      <Card bodyClass="p-0" title={data ? `${data.length} record(s)` : undefined}>
        {loading ? <Spinner /> : error ? <div className="p-5"><ErrorState message={error} onRetry={reload} /></div> : (
          <FdrTable rows={data || []} showInstitution={!isInst} linkTo={(f) => caseLink(user!.role, f.id)}
            empty={<EmptyState title="No FDRs match these filters" message={isInst ? "Upload an FDR to get started." : "Try clearing the filters."}
              action={isInst ? <Link to="/institution/upload" className="btn-teal btn-sm">Upload FDR</Link> : <button className="btn-outline btn-sm" onClick={reset}>Reset filters</button>} />} />
        )}
      </Card>
    </div>
  );
}
