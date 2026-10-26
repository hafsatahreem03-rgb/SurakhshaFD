import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Activity, Database, ExternalLink, Loader2, RotateCcw, ScrollText, Server, X } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDateTime, humanize, inr } from "../lib/format";
import type { AuditEntry } from "../lib/types";
import { Badge, Modal, useToast } from "./ui";

interface ReqEntry { id: number; at: string; method: string; path: string; status: number; ms: number; email: string | null; role: string | null }
interface DbSnap {
  read_at: string; database_file: string | null; database_bytes: number | null; database_modified: string | null;
  row_counts: Record<string, number>;
  latest_fdr_rows: { id: number; reference_no: string; institution: string; fdr_number: string | null; principal_amount: number | null;
    submission_status: string; document_status: string; bank_status: string; is_cleared: boolean; updated_at: string }[];
  latest_audit: AuditEntry[];
}
interface DemoConfig { demo_mode: boolean; database: string; database_file: string | null; api_log_file: string | null; server_started_at: string; bank_adapter: string }

const METHOD_TONE: Record<string, string> = { GET: "bg-slate-100 text-slate-700", POST: "bg-teal-100 text-teal-800", PUT: "bg-blue-100 text-blue-800", PATCH: "bg-violet-100 text-violet-800", DELETE: "bg-red-100 text-red-700" };

const time = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour12: false }) + "." + iso.slice(20, 23);

/** Judge Demonstration Mode: shows live proof that actions run through FastAPI and the database. */
export default function EvidencePanel() {
  const { user } = useAuth();
  const toast = useToast();
  const [config, setConfig] = useState<DemoConfig | null>(null);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"api" | "db" | "audit">("api");
  const [reqs, setReqs] = useState<ReqEntry[]>([]);
  const [snap, setSnap] = useState<DbSnap | null>(null);
  const [delta, setDelta] = useState<Record<string, number>>({});
  const [fresh, setFresh] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [resetting, setResetting] = useState(false);
  const prevCounts = useRef<Record<string, number> | null>(null);
  const lastId = useRef(0);

  useEffect(() => {
    api.get<DemoConfig>("/demo/config").then((r) => setConfig(r.data)).catch(() => setConfig(null));
  }, []);

  useEffect(() => {
    if (!open || !config?.demo_mode) return;
    let alive = true;
    const poll = async () => {
      try {
        const [r, d] = await Promise.all([api.get<ReqEntry[]>("/demo/requests"), api.get<DbSnap>("/demo/db")]);
        if (!alive) return;
        const newIds = r.data.filter((e) => e.id > lastId.current).map((e) => e.id);
        if (lastId.current && newIds.length) {
          setFresh(new Set(newIds));
          setTimeout(() => setFresh(new Set()), 2500);
        }
        lastId.current = Math.max(lastId.current, ...r.data.map((e) => e.id), 0);
        setReqs(r.data);
        if (prevCounts.current) {
          const changed: Record<string, number> = {};
          for (const [k, v] of Object.entries(d.data.row_counts)) {
            const diff = v - (prevCounts.current[k] ?? v);
            if (diff) changed[k] = diff;
          }
          if (Object.keys(changed).length) {
            setDelta(changed);
            setTimeout(() => setDelta({}), 4000);
          }
        }
        prevCounts.current = d.data.row_counts;
        setSnap(d.data);
        setError(null);
      } catch (e) {
        if (alive) setError(errorMessage(e));
      }
    };
    poll();
    const t = setInterval(poll, 2000);
    return () => { alive = false; clearInterval(t); };
  }, [open, config?.demo_mode]);

  if (!config?.demo_mode) return null;

  const doReset = async () => {
    setResetting(true);
    try {
      const r = await api.post("/demo/reset", { confirm });
      toast("success", `Demo data reset. Backup saved: ${r.data.backup ? r.data.backup.split(/[\\/]/).pop() : "none"}`);
      setResetOpen(false);
      setConfirm("");
      setTimeout(() => location.reload(), 900);
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setResetting(false);
    }
  };

  const TABS = [
    { k: "api" as const, label: "API calls", icon: Activity },
    { k: "db" as const, label: "Database", icon: Database },
    { k: "audit" as const, label: "Audit log", icon: ScrollText },
  ];

  return (
    <>
      <button onClick={() => setOpen(true)} data-testid="evidence-button"
        title="Live API, database and audit evidence (Judge Demonstration Mode)"
        className="flex items-center gap-2 rounded-full bg-navy-900 px-3.5 py-1.5 text-xs font-semibold text-white shadow ring-1 ring-white/10 transition hover:bg-navy-800">
        <span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-teal-400" /></span>
        Live Evidence
      </button>

      {/* Portal: the trigger lives in the blurred sticky header, which would otherwise trap this fixed overlay. */}
      {open && createPortal(
        <div className="fixed inset-0 z-40 flex justify-end bg-navy-950/30" onMouseDown={() => setOpen(false)}>
          <aside role="dialog" aria-label="Live execution evidence" onMouseDown={(e) => e.stopPropagation()}
            className="flex h-full w-full max-w-[600px] animate-fadein flex-col bg-white shadow-2xl">
            <header className="border-b border-slate-200 bg-navy-900 px-5 py-4 text-white">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-base font-bold"><Server className="h-4 w-4 text-teal-300" />Live execution evidence</div>
                  <p className="mt-1 text-xs text-navy-200">
                    Read live from the FastAPI server and the {config.database} database every 2 seconds.
                    {user?.role === "institution" ? " As an institution you only see your own requests and records." : ""}
                  </p>
                </div>
                <button onClick={() => setOpen(false)} className="rounded p-1 text-navy-200 hover:bg-white/10" aria-label="Close"><X className="h-5 w-5" /></button>
              </div>
              <div className="mt-3 flex gap-1">
                {TABS.map((t) => (
                  <button key={t.k} onClick={() => setTab(t.k)}
                    className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold ${tab === t.k ? "bg-white text-navy-900" : "text-navy-100 hover:bg-white/10"}`}>
                    <t.icon className="h-3.5 w-3.5" />{t.label}
                  </button>
                ))}
              </div>
            </header>

            <div className="flex-1 overflow-auto p-4 text-sm">
              {error && <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">{error}</div>}
              {!snap && !error && <div className="flex items-center gap-2 py-10 text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />Connecting to the server…</div>}

              {snap && tab === "api" && (
                <div>
                  <p className="mb-3 text-xs text-slate-500">
                    Every request FastAPI received (metadata only, no request bodies or tokens). The same lines print in the
                    <b> backend terminal window</b>{config.api_log_file ? <> and in <code className="rounded bg-slate-100 px-1">{config.api_log_file}</code></> : null}.
                  </p>
                  {reqs.length === 0 ? <div className="text-slate-500">No requests yet. Click around the app.</div> : (
                    <table className="w-full text-xs">
                      <thead><tr className="text-left text-[10px] uppercase tracking-wide text-slate-400"><th className="pb-1">Time</th><th>Request</th><th>Status</th><th className="text-right">ms</th></tr></thead>
                      <tbody>
                        {reqs.map((e) => (
                          <tr key={e.id} className={`border-t border-slate-100 align-top transition-colors ${fresh.has(e.id) ? "bg-teal-50" : ""}`}>
                            <td className="whitespace-nowrap py-1.5 pr-2 font-mono text-[11px] text-slate-500">{time(e.at)}</td>
                            <td className="py-1.5 pr-2">
                              <span className={`mr-1.5 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${METHOD_TONE[e.method] || "bg-slate-100"}`}>{e.method}</span>
                              <span className="break-all font-mono text-[11px] text-navy-900">{e.path}</span>
                              <div className="text-[10px] text-slate-400">{e.email ? `${e.email} · ${e.role}` : "not signed in"}</div>
                            </td>
                            <td className={`py-1.5 pr-2 font-mono font-bold ${e.status < 300 ? "text-emerald-600" : e.status < 500 ? "text-amber-600" : "text-red-600"}`}>{e.status}</td>
                            <td className="py-1.5 text-right font-mono text-[11px] text-slate-500">{e.ms}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {snap && tab === "db" && (
                <div className="space-y-4">
                  <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                    <div><b>File:</b> <code className="break-all">{snap.database_file || config.database}</code></div>
                    <div className="mt-1"><b>Size:</b> {snap.database_bytes ? `${(snap.database_bytes / 1024).toFixed(0)} KB` : "—"} · <b>Last written:</b> {snap.database_modified ? fmtDateTime(snap.database_modified.replace("+00:00", "")) : "—"}</div>
                  </div>
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Rows per table (changes flash green)</div>
                    <div className="grid grid-cols-2 gap-1.5">
                      {Object.entries(snap.row_counts).map(([t, n]) => (
                        <div key={t} className={`flex items-center justify-between rounded-md border px-2.5 py-1.5 font-mono text-[11px] transition-colors ${delta[t] ? "border-teal-400 bg-teal-50" : "border-slate-200"}`}>
                          <span className="truncate text-slate-600">{t}</span>
                          <span className="font-bold text-navy-900">{n}{delta[t] ? <span className="ml-1 text-teal-600">+{delta[t]}</span> : null}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">fdr_records, most recently updated</div>
                    <div className="space-y-1.5">
                      {snap.latest_fdr_rows.map((r) => (
                        <div key={r.id} className="rounded-md border border-slate-200 p-2 font-mono text-[11px]">
                          <div className="flex justify-between gap-2"><b className="text-navy-900">{r.reference_no}</b><span className="text-slate-400">updated {fmtDateTime(r.updated_at)}</span></div>
                          <div className="text-slate-600">{r.fdr_number || "—"} · {inr(r.principal_amount)}</div>
                          <div className="text-slate-500">submission=<b>{r.submission_status}</b> document=<b>{r.document_status}</b> bank=<b>{r.bank_status}</b>{r.bank_status !== "not_started" ? " (simulated)" : ""}{r.is_cleared ? " cleared=true" : ""}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {snap && tab === "audit" && (
                <div>
                  <p className="mb-3 text-xs text-slate-500">Newest first. The audit table is append-only: the database rejects UPDATE and DELETE.</p>
                  <ul className="space-y-2">
                    {snap.latest_audit.map((a) => (
                      <li key={a.id} className="rounded-md border border-slate-200 p-2 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold text-navy-900">#{a.id} {humanize(a.action)}</span>
                          <span className="font-mono text-[11px] text-slate-500">{fmtDateTime(a.created_at)}</span>
                        </div>
                        <div className="text-slate-600">{a.description}</div>
                        <div className="mt-0.5 font-mono text-[10px] text-slate-400">{a.user_email || "system"}{a.role ? ` · ${a.role}` : ""}{a.previous_status || a.new_status ? ` · ${a.previous_status || "∅"} → ${a.new_status || "∅"}` : ""}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <footer className="flex flex-wrap items-center gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs">
              <Badge tone="amber" dot={false}>Bank adapter: {config.bank_adapter}</Badge>
              <a className="btn-outline btn-sm ml-auto" href={import.meta.env.DEV ? "http://localhost:8000/docs" : "/docs"} target="_blank" rel="noreferrer"><ExternalLink className="h-3.5 w-3.5" />API docs</a>
              {user?.role === "admin" && (
                <button className="btn-danger btn-sm" onClick={() => setResetOpen(true)}><RotateCcw className="h-3.5 w-3.5" />Reset demo data</button>
              )}
            </footer>
          </aside>
        </div>,
        document.body,
      )}

      {createPortal(<Modal open={resetOpen} title="Reset demo data" onClose={() => setResetOpen(false)}
        footer={<>
          <button className="btn-outline" onClick={() => setResetOpen(false)}>Cancel</button>
          <button className="btn-danger" disabled={confirm !== "RESET" || resetting} onClick={doReset}>
            {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}Reset now
          </button>
        </>}>
        <p className="text-sm text-slate-600">
          This copies the current database to <code>backend/data/backups</code>, then wipes all records and uploads and reloads the
          fictional demo data. Everyone stays signed in.
        </p>
        <label className="mt-4 block">
          <span className="label">Type RESET to confirm</span>
          <input className="input font-mono" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="RESET" />
        </label>
      </Modal>, document.body)}
    </>
  );
}
