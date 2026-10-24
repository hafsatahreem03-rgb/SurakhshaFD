import { useState } from "react";
import { Link } from "react-router-dom";
import { Download, Lock, RotateCcw } from "lucide-react";
import { downloadFile } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { caseLink, fmtDateTime, humanize } from "../../lib/format";
import type { AuditEntry } from "../../lib/types";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Spinner, Table } from "../../components/ui";

export default function AuditLogs() {
  const { user } = useAuth();
  const [f, setF] = useState({ action: "", user_email: "", date_from: "", date_to: "" });
  const { data, loading, error, reload } = useFetch<AuditEntry[]>("/audit", { ...f, limit: 500 });
  const { data: actions } = useFetch<string[]>("/audit/actions");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle={<span className="flex items-center gap-1"><Lock className="h-3.5 w-3.5" />Append-only. Entries cannot be edited or deleted, including at the database level.</span>}
        actions={<button className="btn-primary" onClick={() => downloadFile("/audit/export.csv", "surakshafd-audit.csv", Object.fromEntries(Object.entries(f).filter(([, v]) => v)))}><Download className="h-4 w-4" />Export CSV</button>} />
      <Card className="mb-4" bodyClass="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <select className="input" value={f.action} onChange={(e) => set("action", e.target.value)}>
            <option value="">All actions</option>
            {actions?.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
          </select>
          <input className="input" placeholder="User email contains…" value={f.user_email} onChange={(e) => set("user_email", e.target.value)} />
          <input type="date" className="input" value={f.date_from} onChange={(e) => set("date_from", e.target.value)} />
          <input type="date" className="input" value={f.date_to} onChange={(e) => set("date_to", e.target.value)} />
          <button className="btn-outline" onClick={() => setF({ action: "", user_email: "", date_from: "", date_to: "" })}><RotateCcw className="h-4 w-4" />Reset</button>
        </div>
      </Card>
      <Card bodyClass="p-0" title={data ? `${data.length} entries (latest first)` : undefined}>
        {loading && !data ? <Spinner /> : error ? <div className="p-5"><ErrorState message={error} onRetry={reload} /></div> : data?.length ? (
          <Table head={["Time", "User", "Action", "Case", "Status change", "Description"]}>
            {data.map((a) => (
              <tr key={a.id} className="align-top">
                <td className="td whitespace-nowrap text-xs text-slate-500">{fmtDateTime(a.created_at)}</td>
                <td className="td text-xs"><div className="font-medium">{a.user_email || "—"}</div><div className="text-slate-500">{humanize(a.role)}</div></td>
                <td className="td"><Badge tone={/fail|blocked|reject/.test(a.action) ? "red" : a.action.startsWith("login") ? "gray" : "teal"}>{humanize(a.action)}</Badge></td>
                <td className="td text-xs">{a.fdr_id ? <Link className="font-medium text-navy-700 hover:underline" to={caseLink(user!.role, a.fdr_id)}>{a.reference_no}</Link> : "—"}</td>
                <td className="td font-mono text-[11px] text-slate-500">{a.previous_status || a.new_status ? `${a.previous_status || "∅"} → ${a.new_status || "∅"}` : ""}</td>
                <td className="td max-w-md text-xs text-slate-600">{a.description}</td>
              </tr>
            ))}
          </Table>
        ) : <EmptyState title="No audit entries match" />}
      </Card>
    </div>
  );
}
