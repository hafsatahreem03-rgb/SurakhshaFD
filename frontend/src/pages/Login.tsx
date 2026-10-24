import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Building2, FileSearch, Gavel, KeyRound, Landmark, Loader2, Lock, Mail, ScrollText, ShieldCheck, UserCog } from "lucide-react";
import { useAuth } from "../lib/auth";
import { errorMessage } from "../lib/api";
import { ROLE_HOME } from "../lib/format";
import { Logo, ShieldMark, TeamLogo } from "../components/Logo";
import { Alert } from "../components/ui";

const DEMO = [
  { email: "aravalli@demo.surakshafd.in", role: "Institution", who: "Aravalli Institute of Technology", icon: Building2 },
  { email: "officer@demo.surakshafd.in", role: "AICTE Officer", who: "Rahul Verma", icon: FileSearch },
  { email: "senior@demo.surakshafd.in", role: "Senior Approver", who: "Dr. S. K. Rao", icon: Gavel },
  { email: "admin@demo.surakshafd.in", role: "Administrator", who: "System Administrator", icon: UserCog },
];
const DEMO_PASSWORD = "Demo@123";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;

  const submit = async (e?: FormEvent, override?: { email: string; password: string }) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(override?.email ?? email, override?.password ?? password);
      navigate(ROLE_HOME[u.role]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-navy-900 via-navy-950 to-[#04101f] p-12 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-teal-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 -left-20 h-96 w-96 rounded-full bg-navy-500/30 blur-3xl" />
        <Logo light />
        <div className="relative my-auto max-w-lg">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-teal-200 ring-1 ring-white/15">
            Smart India Hackathon 2026 · PS 26265 · Team Lynxcode
          </div>
          <h1 className="text-4xl font-extrabold leading-tight text-white">
            Every security deposit,<br />one <span className="text-teal-400">auditable</span> case file.
          </h1>
          <p className="mt-4 text-navy-200">
            Institutions upload FDRs, OCR reads them, automatic checks flag discrepancies, officers verify, and a different senior officer makes the final decision, with every step recorded.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-3 text-sm">
            {[
              [FileSearch, "OCR extraction + validation"],
              [Landmark, "Bank verification adapter (simulated)"],
              [ShieldCheck, "Two-person approval"],
              [ScrollText, "Append-only audit trail"],
            ].map(([Icon, t]: any) => (
              <div key={t} className="flex items-center gap-2 rounded-lg bg-white/5 p-3 ring-1 ring-white/10">
                <Icon className="h-4 w-4 text-teal-400" /> <span className="text-navy-100">{t}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="relative mb-4 flex items-center gap-3">
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-navy-300">Built by</span>
          <TeamLogo badge className="h-6" />
        </div>
        <p className="relative text-xs text-navy-300">
          Demonstration prototype, not an official AICTE service. OCR and automatic checks cannot prove an FDR is genuine; that needs independent confirmation from the issuing bank.
        </p>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center bg-slate-50 px-4 py-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex justify-center lg:hidden"><ShieldMark className="h-14 w-14" /></div>
          <div className="card p-7">
            <h2 className="text-xl font-bold">Sign in to SurakshaFD</h2>
            <p className="mt-1 text-sm text-slate-500">Smart FDR &amp; Security Deposit Management Portal</p>
            {params.get("expired") && <div className="mt-4"><Alert tone="warning">Your session expired. Please sign in again.</Alert></div>}
            <form onSubmit={submit} className="mt-6 space-y-4">
              <label className="block">
                <span className="label">Email</span>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input className="input pl-9" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@institution.in" />
                </div>
              </label>
              <label className="block">
                <span className="label">Password</span>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input className="input pl-9" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
                </div>
              </label>
              {error && <Alert tone="error">{error}</Alert>}
              <button className="btn-primary w-full py-2.5" disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />} Sign in
              </button>
            </form>
          </div>

          <div className="mt-5 rounded-xl border border-dashed border-amber-300 bg-amber-50/70 p-4">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-800">
              <KeyRound className="h-3.5 w-3.5" /> Demo accounts · development only
            </div>
            <p className="mt-1 text-xs text-amber-800">Password for every demo account: <code className="rounded bg-white px-1 font-semibold">{DEMO_PASSWORD}</code>. Click one to sign in.</p>
            <div className="mt-3 grid gap-2">
              {DEMO.map((d) => (
                <button key={d.email} type="button" disabled={busy}
                  onClick={() => { setEmail(d.email); setPassword(DEMO_PASSWORD); submit(undefined, { email: d.email, password: DEMO_PASSWORD }); }}
                  className="flex items-center gap-3 rounded-lg bg-white px-3 py-2 text-left text-sm ring-1 ring-amber-200 transition hover:ring-teal-400">
                  <d.icon className="h-4 w-4 text-navy-600" />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-navy-900">{d.role}</div>
                    <div className="truncate text-xs text-slate-500">{d.email}</div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-300" />
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-amber-700">Each browser tab signs in separately, so you can open institution, officer and senior approver side by side.</p>
            <p className="mt-1 text-[11px] text-amber-700">More: godavari@, narmada@, konark@, brahmaputra@ (institutions), officer2@, senior2@ (same domain).</p>
          </div>
          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500">
            <span>SIH 2026 · PS 26265 · developed by</span>
            <TeamLogo className="h-5" />
          </div>
        </div>
      </div>
    </div>
  );
}
