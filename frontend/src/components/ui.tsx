import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Inbox, Info, Loader2, X, XCircle } from "lucide-react";
import { BANK_STATUS, CLEARANCE_STATUS, DOC_STATUS, STAGES, type Tone } from "../lib/format";

const TONES: Record<Tone, string> = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  teal: "bg-teal-50 text-teal-700 ring-teal-200",
  purple: "bg-violet-50 text-violet-700 ring-violet-200",
  navy: "bg-navy-50 text-navy-700 ring-navy-200",
};

export function Badge({ tone = "gray", children, dot = true }: { tone?: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />}
      {children}
    </span>
  );
}

type StatusKind = "stage" | "document" | "bank" | "clearance";
const MAPS = { stage: STAGES, document: DOC_STATUS, bank: BANK_STATUS, clearance: CLEARANCE_STATUS };

export function StatusBadge({ kind, value }: { kind: StatusKind; value: string | null | undefined }) {
  if (!value) return <span className="text-slate-400">—</span>;
  const [label, tone] = MAPS[kind][value] || [value, "gray" as Tone];
  return <Badge tone={tone}>{label}</Badge>;
}

export function SimulatedTag({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded border border-dashed border-amber-400 bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-800 ${className}`}>
      Demo / Simulated
    </span>
  );
}

export function Card({ title, subtitle, action, children, className = "", bodyClass = "p-5" }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`card animate-fadein ${className}`}>
      {(title || action) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            {title && <h3 className="text-sm font-semibold">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function StatCard({ label, value, icon: Icon, tone = "navy", hint, onClick }: {
  label: string; value: ReactNode; icon: any; tone?: "navy" | "teal" | "amber" | "red" | "green" | "purple"; hint?: string; onClick?: () => void;
}) {
  const iconTone = {
    navy: "bg-navy-50 text-navy-700", teal: "bg-teal-50 text-teal-700", amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-600", green: "bg-emerald-50 text-emerald-700", purple: "bg-violet-50 text-violet-700",
  }[tone];
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      className="card group flex w-full items-start gap-4 p-4 text-left transition enabled:hover:-translate-y-0.5 enabled:hover:shadow-lg disabled:cursor-default">
      <div className={`rounded-xl p-2.5 ${iconTone}`}><Icon className="h-5 w-5" /></div>
      <div className="min-w-0">
        <div className="text-xs font-medium text-slate-500">{label}</div>
        <div className="mt-0.5 truncate text-2xl font-bold text-navy-900">{value}</div>
        {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
      </div>
    </button>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
      <Loader2 className="h-5 w-5 animate-spin text-teal-600" /> {label}
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="rounded-full bg-slate-100 p-3"><Inbox className="h-6 w-6 text-slate-400" /></div>
      <div className="font-semibold text-slate-700">{title}</div>
      {message && <p className="max-w-md text-sm text-slate-500">{message}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
      <XCircle className="h-6 w-6" />
      <div>{message}</div>
      {onRetry && <button className="btn-outline btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Alert({ tone = "info", title, children }: { tone?: "info" | "warning" | "error" | "success"; title?: string; children?: ReactNode }) {
  const cfg = {
    info: ["border-blue-200 bg-blue-50 text-blue-800", Info],
    warning: ["border-amber-200 bg-amber-50 text-amber-900", AlertTriangle],
    error: ["border-red-200 bg-red-50 text-red-800", XCircle],
    success: ["border-emerald-200 bg-emerald-50 text-emerald-800", CheckCircle2],
  }[tone] as [string, any];
  const Icon = cfg[1];
  return (
    <div className={`flex gap-3 rounded-lg border p-3 text-sm ${cfg[0]}`}>
      <Icon className="mt-0.5 h-4 w-4 flex-none" />
      <div>
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
    </div>
  );
}

export function Modal({ open, title, onClose, children, footer, wide }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/50 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div className={`card w-full animate-fadein ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[90vh] overflow-auto`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Field({ label, children, hint, error }: { label: string; children: ReactNode; hint?: ReactNode; error?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {error ? <span className="mt-1 block text-xs text-red-600">{error}</span> : hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
    </label>
  );
}

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100">
        <thead className="bg-slate-50/70"><tr>{head.map((h, i) => <th key={i} className="th">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}

// ---------------- toasts ----------------
type Toast = { id: number; tone: "success" | "error" | "info"; text: string };
const ToastCtx = createContext<(tone: Toast["tone"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={`flex animate-fadein items-start gap-2 rounded-lg px-4 py-3 text-sm text-white shadow-lg ${t.tone === "success" ? "bg-emerald-600" : t.tone === "error" ? "bg-red-600" : "bg-navy-800"}`}>
            {t.tone === "success" ? <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none" /> : t.tone === "error" ? <XCircle className="mt-0.5 h-4 w-4 flex-none" /> : <Info className="mt-0.5 h-4 w-4 flex-none" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
