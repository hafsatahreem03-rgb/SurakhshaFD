import { Link, useNavigate } from "react-router-dom";
import {
  AlarmClock, AlertTriangle, BadgeCheck, Building2, CalendarClock, CheckCircle2, ClipboardList, FileText, FileUp, Gavel,
  Hourglass, IndianRupee, Landmark, Stamp, Users, XCircle,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { BANK_STATUS, STAGES, caseLink, fmtDate, humanize, inr, timeAgo } from "../../lib/format";
import type { AuditEntry, FDR, Role } from "../../lib/types";
import { MaturityBadge } from "../../components/fdr";
import { Card, EmptyState, ErrorState, PageHeader, Spinner, StatCard, StatusBadge } from "../../components/ui";

interface DashData {
  cards: Record<string, number>;
  stage_distribution: { stage: string; count: number }[];
  bank_distribution: { status: string; count: number }[];
  upcoming_maturities: FDR[];
  recent_fdrs: FDR[];
  recent_activity: AuditEntry[];
}

const TONE_HEX: Record<string, string> = {
  gray: "#94a3b8", blue: "#3b82f6", amber: "#f59e0b", red: "#ef4444", green: "#10b981", teal: "#14b8a6", purple: "#8b5cf6", navy: "#1f4485",
};

const TITLES: Record<Role, [string, string]> = {
  institution: ["Institution Dashboard", "Your security deposits and FDRs at a glance"],
  officer: ["Officer Dashboard", "Cases needing scrutiny, verification and deadline action"],
  senior: ["Approval Dashboard", "Clearance requests awaiting your final decision"],
  admin: ["Overall Dashboard", "Portal-wide deposits, verification and clearance statistics"],
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, loading, error, reload } = useFetch<DashData>("/dashboard");
  if (!user) return null;
  const role = user.role;
  const base = `/${role}`;

  if (loading) return <Spinner />;
  if (error || !data) return <ErrorState message={error || "No data"} onRetry={reload} />;
  const c = data.cards;

  const cardsByRole: Record<Role, any[]> = {
    institution: [
      ["Total FDRs submitted", c.submitted_fdrs, FileText, "navy", `${c.drafts} draft(s)`, `${base}/fdrs`],
      ["Total deposited amount", inr(c.total_amount, true), IndianRupee, "teal", "submitted FDRs", `${base}/fdrs`],
      ["Pending verification", c.pending_verification, Hourglass, "amber", "bank check not completed", `${base}/fdrs`],
      ["Discrepancies", c.discrepancies, AlertTriangle, "red", `${c.correction_requested} correction(s) requested`, `${base}/fdrs`],
      ["Bank-confirmed (demo)", c.bank_confirmed, BadgeCheck, "green", "simulated confirmations", `${base}/fdrs`],
      ["Approaching maturity", c.approaching_maturity, CalendarClock, "purple", `within 60 days · ${c.matured} matured`, `${base}/fdrs`],
      ["Pending clearance", c.pending_clearance + c.awaiting_final_decision, Stamp, "navy", `${c.cleared} cleared (demo)`, `${base}/clearances`],
    ],
    officer: [
      ["Pending document review", c.pending_document_review, ClipboardList, "navy", `${c.overdue_reviews} overdue`, `${base}/cases?document_status=pending_review`],
      ["Discrepancies flagged", c.discrepancies, AlertTriangle, "red", "validation or bank mismatch", `${base}/cases`],
      ["Awaiting bank verification", c.pending_verification, Landmark, "amber", "simulated adapter", `${base}/bank`],
      ["Bank-confirmed (demo)", c.bank_confirmed, BadgeCheck, "green", undefined, `${base}/cases?bank_status=confirmed`],
      ["Maturing ≤ 60 days", c.approaching_maturity, CalendarClock, "purple", `${c.matured} already matured`, `${base}/cases?maturing_within_days=60`],
      ["Clearance requests", c.pending_clearance, Stamp, "teal", `${c.awaiting_final_decision} with senior`, `${base}/clearances`],
    ],
    senior: [
      ["Awaiting your decision", c.awaiting_final_decision, Gavel, "purple", "recommended by officers", `${base}/approvals`],
      ["With officers", c.pending_clearance, Hourglass, "amber", "not yet recommended", undefined],
      ["Approved (demo)", c.clearances_approved, CheckCircle2, "green", undefined, `${base}/approvals?tab=decided`],
      ["Rejected", c.clearances_rejected, XCircle, "red", undefined, `${base}/approvals?tab=decided`],
      ["Total deposits on record", inr(c.total_amount, true), IndianRupee, "teal", `${c.submitted_fdrs} FDRs`, `${base}/cases`],
      ["Maturing ≤ 60 days", c.approaching_maturity, CalendarClock, "navy", `${c.matured} matured`, `${base}/cases`],
    ],
    admin: [
      ["Institutions", c.institutions, Building2, "navy", undefined, `${base}/users`],
      ["Users", c.users, Users, "purple", undefined, `${base}/users`],
      ["FDRs on record", c.submitted_fdrs, FileText, "teal", inr(c.total_amount, true), `${base}/cases`],
      ["Pending review", c.pending_document_review, ClipboardList, "amber", `${c.overdue_reviews} overdue`, `${base}/cases`],
      ["Bank-confirmed (demo)", c.bank_confirmed, BadgeCheck, "green", undefined, `${base}/reports`],
      ["Discrepancies", c.discrepancies, AlertTriangle, "red", undefined, `${base}/reports`],
      ["Maturing ≤ 60 days", c.approaching_maturity, AlarmClock, "purple", `${c.matured} matured`, `${base}/cases`],
      ["Cleared (demo)", c.cleared, Stamp, "navy", `${c.awaiting_final_decision} awaiting decision`, `${base}/reports`],
    ],
  };

  const stageData = data.stage_distribution.map((s) => ({ name: STAGES[s.stage]?.[0] || humanize(s.stage), value: s.count, fill: TONE_HEX[STAGES[s.stage]?.[1] || "gray"] }));
  const bankData = data.bank_distribution.map((s) => ({ name: (BANK_STATUS[s.status]?.[0] || s.status).replace(" · simulated", ""), value: s.count, fill: TONE_HEX[BANK_STATUS[s.status]?.[1] || "gray"] }));

  return (
    <div>
      <PageHeader title={TITLES[role][0]} subtitle={role === "institution" ? user.institution_name : TITLES[role][1]}
        actions={role === "institution" ? <Link to="/institution/upload" className="btn-teal"><FileUp className="h-4 w-4" />Upload new FDR</Link>
          : role === "senior" ? <Link to="/senior/approvals" className="btn-primary"><Gavel className="h-4 w-4" />Review pending approvals</Link>
          : role === "officer" ? <Link to="/officer/cases?document_status=pending_review" className="btn-primary"><ClipboardList className="h-4 w-4" />Open review queue</Link> : undefined} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cardsByRole[role].map(([label, value, icon, tone, hint, to]) => (
          <StatCard key={label} label={label} value={value ?? 0} icon={icon} tone={tone} hint={hint} onClick={to ? () => navigate(to) : undefined} />
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Case stage distribution" subtitle="Each FDR's current workflow stage" className="lg:col-span-2">
          {stageData.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={stageData} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={60} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="value" name="FDRs" radius={[6, 6, 0, 0]}>{stageData.map((d, i) => <Cell key={i} fill={d.fill} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState title="No cases yet" />}
        </Card>
        <Card title="Bank verification status" subtitle="All outcomes are simulated in this demo">
          {bankData.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={bankData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {bankData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <EmptyState title="No verifications yet" />}
          <div className="flex flex-wrap justify-center gap-3 text-xs">
            {bankData.map((d) => <span key={d.name} className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: d.fill }} />{d.name} ({d.value})</span>)}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Upcoming maturities" subtitle="Alerts are raised at 60, 30 and 7 days (demo policy)" bodyClass="p-0">
          {data.upcoming_maturities.length ? (
            <ul className="divide-y divide-slate-100">
              {data.upcoming_maturities.map((f) => (
                <li key={f.id}>
                  <Link to={caseLink(role, f.id)} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50">
                    <CalendarClock className="h-4 w-4 text-slate-400" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-navy-800">{f.reference_no} · <span className="font-mono text-xs">{f.fdr_number}</span></div>
                      <div className="truncate text-xs text-slate-500">{role !== "institution" && `${f.institution_name} · `}{inr(f.principal_amount)} · matures {fmtDate(f.maturity_date)}</div>
                    </div>
                    <MaturityBadge days={f.days_to_maturity} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="Nothing maturing in the next 60 days" />}
        </Card>
        <Card title="Recent activity" subtitle="From the audit trail" bodyClass="p-0">
          {data.recent_activity.length ? (
            <ul className="divide-y divide-slate-100">
              {data.recent_activity.slice(0, 8).map((a) => (
                <li key={a.id}>
                  <Link to={a.fdr_id ? caseLink(role, a.fdr_id) : "#"} className="flex gap-3 px-5 py-3 hover:bg-slate-50">
                    <span className="mt-1.5 h-2 w-2 flex-none rounded-full bg-teal-500" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm"><span className="font-semibold text-navy-800">{humanize(a.action)}</span> <span className="text-slate-400">· {a.reference_no}</span></div>
                      <div className="truncate text-xs text-slate-500">{a.description}</div>
                    </div>
                    <span className="whitespace-nowrap text-xs text-slate-400">{timeAgo(a.created_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No activity yet" />}
        </Card>
      </div>

      {role !== "institution" && (
        <Card title="Latest submissions" subtitle="Updates as soon as an institution submits" className="mt-6" bodyClass="p-0"
          action={<Link to={`${base}/cases`} className="text-sm font-medium text-teal-700 hover:underline">All cases</Link>}>
          {data.recent_fdrs.length ? (
            <ul className="divide-y divide-slate-100">
              {data.recent_fdrs.map((f) => (
                <li key={f.id}>
                  <Link to={caseLink(role, f.id)} className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-slate-50">
                    <div className="min-w-[140px] font-semibold text-navy-800">{f.reference_no}</div>
                    <div className="min-w-0 flex-1 truncate text-sm text-slate-600">{f.institution_name} · {f.bank_name} · {inr(f.principal_amount)}</div>
                    <span className="text-xs text-slate-400">{timeAgo(f.updated_at)}</span>
                    <StatusBadge kind="stage" value={f.stage} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No submissions yet" />}
        </Card>
      )}

      {role === "institution" && (
        <Card title="Recent submissions" className="mt-6" bodyClass="p-0" action={<Link to="/institution/fdrs" className="text-sm font-medium text-teal-700 hover:underline">View all</Link>}>
          {data.recent_fdrs.length ? (
            <ul className="divide-y divide-slate-100">
              {data.recent_fdrs.map((f) => (
                <li key={f.id}>
                  <Link to={`/institution/fdrs/${f.id}`} className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-slate-50">
                    <div className="min-w-[140px] font-semibold text-navy-800">{f.reference_no}</div>
                    <div className="flex-1 text-sm text-slate-600">{f.bank_name || "Draft"} · {inr(f.principal_amount)}</div>
                    <StatusBadge kind="stage" value={f.stage} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No FDRs yet" action={<Link to="/institution/upload" className="btn-teal btn-sm">Upload your first FDR</Link>} />}
        </Card>
      )}
    </div>
  );
}
