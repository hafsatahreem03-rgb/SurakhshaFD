import { useState } from "react";
import { History, Loader2, Pencil, Plus } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/useFetch";
import { fmtDate, fmtDateTime } from "../../lib/format";
import { Alert, Badge, Card, ErrorState, Field, Modal, PageHeader, Spinner, useToast } from "../../components/ui";

interface Policy {
  id: number; key: string; name: string; category: string; description: string; current_value: Record<string, unknown>;
  versions: { id: number; version: number; value: Record<string, unknown>; effective_from: string; change_note: string; created_by: string; created_at: string }[];
}

const today = () => new Date().toISOString().slice(0, 10);

export default function Policies() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch<Policy[]>("/policies");
  const [editing, setEditing] = useState<Policy | null>(null);
  const [history, setHistory] = useState<Policy | null>(null);
  const [creating, setCreating] = useState(false);
  const [json, setJson] = useState("");
  const [effective, setEffective] = useState(today());
  const [note, setNote] = useState("");
  const [meta, setMeta] = useState({ key: "", name: "", category: "", description: "" });
  const [busy, setBusy] = useState(false);
  const isAdmin = user?.role === "admin";

  const startEdit = (p: Policy) => {
    setEditing(p);
    setJson(JSON.stringify(p.current_value, null, 2));
    setEffective(today());
    setNote("");
  };

  const save = async () => {
    let value: Record<string, unknown>;
    try {
      value = JSON.parse(json);
    } catch {
      toast("error", "The policy value is not valid JSON.");
      return;
    }
    setBusy(true);
    try {
      if (creating) await api.post("/policies", { ...meta, value, effective_from: effective, change_note: note || "Created" });
      else await api.post(`/policies/${editing!.key}/versions`, { value, effective_from: effective, change_note: note });
      toast("success", creating ? "Policy created." : "New policy version saved.");
      setEditing(null);
      setCreating(false);
      reload();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Policy Management" subtitle="Versioned rules used by validation, alerts and clearance. Changes take effect from their effective date and are audited."
        actions={isAdmin && <button className="btn-primary" onClick={() => { setCreating(true); setEditing(null); setJson("{\n  \n}"); setNote(""); setMeta({ key: "", name: "", category: "", description: "" }); }}><Plus className="h-4 w-4" />New policy</button>} />
      <div className="mb-4"><Alert tone="warning" title="Fictional demonstration values">These are sample rules for the prototype. They are not legally binding AICTE requirements, and the amounts are not official.</Alert></div>
      {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={reload} /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data?.map((p) => (
            <Card key={p.key} title={p.name} subtitle={<span className="font-mono">{p.key}</span>}
              action={<div className="flex gap-2"><Badge tone="navy" dot={false}>v{p.versions[0]?.version}</Badge><Badge tone="teal" dot={false}>{p.category}</Badge></div>}>
              <p className="mb-3 text-sm text-slate-600">{p.description}</p>
              <pre className="overflow-auto rounded-lg bg-navy-950 p-3 font-mono text-xs text-teal-200">{JSON.stringify(p.current_value, null, 2)}</pre>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                Effective from {fmtDate(p.versions[0]?.effective_from)} · {p.versions[0]?.created_by}
                <div className="ml-auto flex gap-2">
                  <button className="btn-outline btn-sm" onClick={() => setHistory(p)}><History className="h-3.5 w-3.5" />History ({p.versions.length})</button>
                  {isAdmin && <button className="btn-primary btn-sm" onClick={() => startEdit(p)}><Pencil className="h-3.5 w-3.5" />New version</button>}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!editing || creating} title={creating ? "Create policy" : `New version · ${editing?.name}`} onClose={() => { setEditing(null); setCreating(false); }} wide
        footer={<><button className="btn-outline" onClick={() => { setEditing(null); setCreating(false); }}>Cancel</button>
          <button className="btn-primary" disabled={busy || (!creating && note.trim().length < 3)} onClick={save}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></>}>
        <div className="grid gap-3">
          {creating && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Key" hint="lowercase_with_underscores"><input className="input font-mono" value={meta.key} onChange={(e) => setMeta({ ...meta, key: e.target.value })} /></Field>
              <Field label="Category"><input className="input" value={meta.category} onChange={(e) => setMeta({ ...meta, category: e.target.value })} /></Field>
              <div className="sm:col-span-2"><Field label="Name"><input className="input" value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} /></Field></div>
              <div className="sm:col-span-2"><Field label="Description"><input className="input" value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} /></Field></div>
            </div>
          )}
          <Field label="Value (JSON)"><textarea className="input min-h-[180px] font-mono text-xs" value={json} onChange={(e) => setJson(e.target.value)} /></Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Effective from"><input type="date" className="input" value={effective} onChange={(e) => setEffective(e.target.value)} /></Field>
            <Field label="Change note (required)"><input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why is this changing?" /></Field>
          </div>
        </div>
      </Modal>

      <Modal open={!!history} title={`Version history · ${history?.name}`} onClose={() => setHistory(null)} wide>
        <ol className="space-y-3">
          {history?.versions.map((v) => (
            <li key={v.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge tone="navy" dot={false}>v{v.version}</Badge>
                <span className="font-medium">{v.change_note}</span>
                <span className="ml-auto text-xs text-slate-500">effective {fmtDate(v.effective_from)} · by {v.created_by} · {fmtDateTime(v.created_at)}</span>
              </div>
              <pre className="mt-2 overflow-auto rounded bg-slate-50 p-2 font-mono text-xs">{JSON.stringify(v.value, null, 2)}</pre>
            </li>
          ))}
        </ol>
      </Modal>
    </div>
  );
}
