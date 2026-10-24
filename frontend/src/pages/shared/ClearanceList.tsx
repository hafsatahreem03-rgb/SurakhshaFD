import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { fmtDateTime, inr } from "../../lib/format";
import type { Clearance } from "../../lib/types";
import { Alert, Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge, Table } from "../../components/ui";

/** Institution: "Clearance Requests". Officer: "Clearance Review". Senior: "Pending Approvals". */
export default function ClearanceList() {
  const { user } = useAuth();
  const role = user!.role;
  const [params] = useSearchParams();
  const tabs = role === "senior"
    ? [{ key: "awaiting_decision", label: "Awaiting my decision" }, { key: "decided", label: "Decided" }, { key: "", label: "All" }]
    : role === "officer"
      ? [{ key: "pending_officer_review", label: "Awaiting officer review" }, { key: "awaiting_decision", label: "With senior approver" }, { key: "decided", label: "Decided" }, { key: "", label: "All" }]
      : [{ key: "", label: "All" }];
  const [tab, setTab] = useState(params.get("tab") || tabs[0].key);
  const { data, loading, error, reload } = useFetch<Clearance[]>("/clearance-requests", { status: tab });

  const link = (c: Clearance) => role === "senior" ? `/senior/decisions/${c.id}` : role === "officer" ? `/officer/clearances/${c.id}` : `/institution/fdrs/${c.fdr_id}?tab=clearance`;
  const titles = { institution: "Clearance Requests", officer: "Clearance Review", senior: "Pending Approvals", admin: "Clearances" };

  return (
    <div>
      <PageHeader title={titles[role]} subtitle={role === "institution"
        ? "Request clearance from an FDR's page once it is document-checked and bank-confirmed."
        : role === "senior" ? "Final decisions require mandatory remarks. You cannot decide a request you recommended." : "Review institution requests and recommend approval or rejection."} />
      {role === "institution" && <div className="mb-4"><Alert tone="info">A demo approval only records a decision in SurakshaFD. Actual release of bank funds happens outside this system.</Alert></div>}
      {tabs.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)} className={`rounded-full px-3 py-1 text-sm font-medium ${tab === t.key ? "bg-navy-800 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{t.label}</button>
          ))}
        </div>
      )}
      <Card bodyClass="p-0">
        {loading ? <Spinner /> : error ? <div className="p-5"><ErrorState message={error} onRetry={reload} /></div> : data?.length ? (
          <Table head={["Request", "FDR", ...(role !== "institution" ? ["Institution"] : []), "Principal", "Requested", "Officer recommendation", "Status", ""]}>
            {data.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50/70">
                <td className="td font-semibold text-navy-700">CR-{String(c.id).padStart(4, "0")}</td>
                <td className="td"><div className="font-medium">{c.fdr?.reference_no}</div><div className="font-mono text-xs text-slate-500">{c.fdr?.fdr_number}</div></td>
                {role !== "institution" && <td className="td max-w-[180px] truncate">{c.fdr?.institution_name}</td>}
                <td className="td font-semibold">{inr(c.fdr?.principal_amount)}</td>
                <td className="td text-xs">{fmtDateTime(c.created_at)}<div className="text-slate-500">{c.requested_by}</div></td>
                <td className="td text-xs">{c.recommendation ? <><b className={c.recommendation === "approve" ? "text-emerald-700" : "text-red-700"}>{c.recommendation}</b><div className="text-slate-500">{c.recommended_by}</div></> : "—"}</td>
                <td className="td"><StatusBadge kind="clearance" value={c.status} /></td>
                <td className="td text-right"><Link className="btn-outline btn-sm" to={link(c)}>{role === "senior" && c.status.startsWith("recommended") ? "Decide" : role === "officer" && c.status === "pending_officer_review" ? "Review" : "Open"}</Link></td>
              </tr>
            ))}
          </Table>
        ) : <EmptyState title="No clearance requests here" />}
      </Card>
    </div>
  );
}
