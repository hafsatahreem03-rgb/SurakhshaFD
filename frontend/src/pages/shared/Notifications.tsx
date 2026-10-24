import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertOctagon, AlertTriangle, BellRing, CheckCheck, CheckCircle2, Info, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { fmtDateTime, resolveLink } from "../../lib/format";
import type { Notification } from "../../lib/types";
import { Card, EmptyState, ErrorState, PageHeader, Spinner, useToast } from "../../components/ui";

const ICON = { info: Info, warning: AlertTriangle, critical: AlertOctagon, success: CheckCircle2 };
const TONE = { info: "text-blue-600 bg-blue-50", warning: "text-amber-600 bg-amber-50", critical: "text-red-600 bg-red-50", success: "text-emerald-600 bg-emerald-50" };

export default function Notifications() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const { data, loading, error, reload, setData } = useFetch<Notification[]>("/notifications", { unread_only: filter === "unread" });
  const [running, setRunning] = useState(false);

  const changed = () => window.dispatchEvent(new Event("notifications-changed"));

  const open = async (n: Notification) => {
    if (!n.is_read) {
      await api.post(`/notifications/${n.id}/read`);
      setData((d) => d?.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)) || null);
      changed();
    }
    const to = user && resolveLink(user.role, n.link);
    if (to) navigate(to);
  };

  const toggle = async (n: Notification) => {
    await api.post(`/notifications/${n.id}/read`, null, { params: { read: !n.is_read } });
    setData((d) => d?.map((x) => (x.id === n.id ? { ...x, is_read: !n.is_read } : x)) || null);
    changed();
  };

  const readAll = async () => {
    await api.post("/notifications/read-all");
    reload();
    changed();
  };

  const runAlerts = async () => {
    setRunning(true);
    try {
      const r = await api.post("/admin/run-alerts");
      const total = Object.entries(r.data).filter(([k]) => k !== "ran_at").reduce((s, [, v]) => s + Number(v), 0);
      toast("success", `Deadline check complete: ${total} new alert(s) created.`);
      reload();
      changed();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setRunning(false);
    }
  };

  const unread = data?.filter((n) => !n.is_read).length || 0;
  return (
    <div>
      <PageHeader title="Notification Centre" subtitle="Deadline alerts and workflow updates. In-app only; no SMS or email is sent."
        actions={<>
          {(user?.role === "admin" || user?.role === "officer") && (
            <button className="btn-outline" onClick={runAlerts} disabled={running}><RefreshCw className={`h-4 w-4 ${running ? "animate-spin" : ""}`} />Run deadline check now</button>
          )}
          <button className="btn-primary" onClick={readAll} disabled={!unread}><CheckCheck className="h-4 w-4" />Mark all read</button>
        </>} />
      <div className="mb-4 flex gap-2">
        {(["all", "unread"] as const).map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={`rounded-full px-3 py-1 text-sm font-medium ${filter === f ? "bg-navy-800 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>
            {f === "all" ? "All" : "Unread"}
          </button>
        ))}
      </div>
      <Card bodyClass="p-0">
        {loading ? <Spinner /> : error ? <div className="p-5"><ErrorState message={error} onRetry={reload} /></div> : !data?.length ? (
          <EmptyState title="You're all caught up" message="New alerts appear here when deadlines approach or a case changes." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.map((n) => {
              const Icon = ICON[n.severity] || BellRing;
              return (
                <li key={n.id} className={`flex gap-3 px-5 py-4 ${n.is_read ? "" : "bg-teal-50/40"}`}>
                  <span className={`flex h-9 w-9 flex-none items-center justify-center rounded-full ${TONE[n.severity]}`}><Icon className="h-4 w-4" /></span>
                  <button className="min-w-0 flex-1 text-left" onClick={() => open(n)}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`text-sm ${n.is_read ? "font-medium text-slate-700" : "font-bold text-navy-900"}`}>{n.title}</span>
                      {!n.is_read && <span className="h-2 w-2 rounded-full bg-teal-500" />}
                    </div>
                    <div className="text-sm text-slate-600">{n.message}</div>
                    <div className="mt-1 text-xs text-slate-400">{fmtDateTime(n.created_at)}</div>
                  </button>
                  <button className="self-start text-xs font-medium text-teal-700 hover:underline" onClick={() => toggle(n)}>
                    Mark {n.is_read ? "unread" : "read"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
