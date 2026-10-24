import { useState } from "react";
import { Download, RotateCcw } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { downloadFile } from "../../lib/api";
import { useFetch } from "../../lib/useFetch";
import { BANK_STATUS, CLEARANCE_STATUS, DOC_STATUS, STAGES, humanize, inr } from "../../lib/format";
import { Card, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from "../../components/ui";
import { AlertTriangle, ClipboardList, FileText, IndianRupee } from "lucide-react";

interface Summary {
  total_count: number; total_amount: number; pending_cases: number;
  stage_distribution: { name: string; value: number }[];
  document_status: { name: string; value: number }[];
  bank_status: { name: string; value: number }[];
  by_institution: { name: string; count: number; amount: number }[];
  maturity_timeline: { month: string; count: number; amount: number }[];
  submissions_by_month: { month: string; count: number }[];
  clearance_status: { name: string; value: number }[];
  validation_issues: { name: string; value: number }[];
}

const PALETTE = ["#1f4485", "#12b09a", "#f59e0b", "#8b5cf6", "#ef4444", "#3b82f6", "#10b981", "#64748b"];

function Donut({ data, labels }: { data: { name: string; value: number }[]; labels: Record<string, [string, string]> }) {
  if (!data.length) return <EmptyState title="No data" />;
  const rows = data.map((d) => ({ name: (labels[d.name]?.[0] || humanize(d.name)).replace(" · simulated", ""), value: d.value }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={rows} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
          {rows.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
        </Pie>
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export default function Reports() {
  const [f, setF] = useState({ institution_id: "", stage: "", date_from: "", date_to: "" });
  const { data, loading, error, reload } = useFetch<Summary>("/reports/summary", f);
  const { data: insts } = useFetch<{ id: number; name: string }[]>("/institutions");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));

  return (
    <div>
      <PageHeader title="Reports & Analytics" subtitle="Filter by institution, stage and creation date; export the matching records as CSV"
        actions={<button className="btn-primary" onClick={() => downloadFile("/reports/fdrs.csv", "surakshafd-fdr-report.csv", params)}><Download className="h-4 w-4" />Export CSV</button>} />

      <Card className="mb-6" bodyClass="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <select className="input" value={f.institution_id} onChange={(e) => set("institution_id", e.target.value)}>
            <option value="">All institutions</option>
            {insts?.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
          <select className="input" value={f.stage} onChange={(e) => set("stage", e.target.value)}>
            <option value="">All stages</option>
            {Object.entries(STAGES).filter(([k]) => k !== "draft").map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <input type="date" className="input" value={f.date_from} onChange={(e) => set("date_from", e.target.value)} title="From" />
          <input type="date" className="input" value={f.date_to} onChange={(e) => set("date_to", e.target.value)} title="To" />
          <button className="btn-outline" onClick={() => setF({ institution_id: "", stage: "", date_from: "", date_to: "" })}><RotateCcw className="h-4 w-4" />Reset</button>
        </div>
      </Card>

      {loading && !data ? <Spinner /> : error || !data ? <ErrorState message={error || "No data"} onRetry={reload} /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="FDR submissions" value={data.total_count} icon={FileText} tone="navy" />
            <StatCard label="Total principal" value={inr(data.total_amount, true)} icon={IndianRupee} tone="teal" />
            <StatCard label="Pending document review" value={data.pending_cases} icon={ClipboardList} tone="amber" />
            <StatCard label="Validation issues (open)" value={data.validation_issues.reduce((s, x) => s + x.value, 0)} icon={AlertTriangle} tone="red" />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card title="Verification status (simulated)"><Donut data={data.bank_status} labels={BANK_STATUS as any} /></Card>
            <Card title="Document review status"><Donut data={data.document_status} labels={DOC_STATUS as any} /></Card>
            <Card title="Clearance requests"><Donut data={data.clearance_status} labels={CLEARANCE_STATUS as any} /></Card>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card title="Deposits by institution" subtitle="Total principal (₹)">
              {data.by_institution.length ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={data.by_institution.map((d) => ({ ...d, short: d.name.replace(" (Demo)", "").split(" ").slice(0, 2).join(" ") }))} layout="vertical" margin={{ left: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                    <XAxis type="number" tickFormatter={(v) => inr(v, true)} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="short" width={120} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => inr(v)} />
                    <Bar dataKey="amount" name="Principal" fill="#1f4485" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <EmptyState title="No data" />}
            </Card>
            <Card title="Maturity timeline" subtitle="Principal maturing per month">
              {data.maturity_timeline.length ? (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={data.maturity_timeline}>
                    <defs><linearGradient id="mat" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#12b09a" stopOpacity={0.4} /><stop offset="100%" stopColor="#12b09a" stopOpacity={0} /></linearGradient></defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(v) => inr(v, true)} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number, n) => (n === "amount" ? inr(v) : v)} />
                    <Area type="monotone" dataKey="amount" stroke="#0b8e7e" fill="url(#mat)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : <EmptyState title="No data" />}
            </Card>
            <Card title="Validation issues by type" subtitle="Errors and warnings in the latest run of each FDR">
              {data.validation_issues.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data.validation_issues.map((d) => ({ ...d, label: humanize(d.name.toLowerCase()) }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={60} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="value" name="FDRs" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <EmptyState title="No open validation issues" />}
            </Card>
            <Card title="Submissions by month">
              {data.submissions_by_month.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data.submissions_by_month}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" name="Submissions" fill="#12b09a" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <EmptyState title="No data" />}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
