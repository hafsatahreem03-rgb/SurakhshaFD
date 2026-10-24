import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3, Bell, Building2, ClipboardCheck, FileCheck2, FileText, FileUp, Gavel, Landmark, LayoutDashboard, LogOut,
  Menu, ScrollText, Settings2, ShieldCheck, Stamp, Users, X,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { ROLE_LABEL } from "../lib/format";
import type { Role } from "../lib/types";
import { Logo, TeamLogo } from "./Logo";
import EvidencePanel from "./EvidencePanel";

type NavItem = { to: string; label: string; icon: any; end?: boolean };

const NAV: Record<Role, NavItem[]> = {
  institution: [
    { to: "/institution", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/institution/fdrs", label: "My FDRs", icon: FileText },
    { to: "/institution/upload", label: "Upload FDR", icon: FileUp },
    { to: "/institution/clearances", label: "Clearance Requests", icon: Stamp },
    { to: "/institution/notifications", label: "Notifications", icon: Bell },
  ],
  officer: [
    { to: "/officer", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/officer/cases", label: "All / Pending Cases", icon: ClipboardCheck },
    { to: "/officer/bank", label: "Bank Verification", icon: Landmark },
    { to: "/officer/clearances", label: "Clearance Review", icon: Stamp },
    { to: "/officer/reports", label: "Reports", icon: BarChart3 },
    { to: "/officer/notifications", label: "Notifications", icon: Bell },
  ],
  senior: [
    { to: "/senior", label: "Approval Dashboard", icon: LayoutDashboard, end: true },
    { to: "/senior/approvals", label: "Pending Approvals", icon: Gavel },
    { to: "/senior/cases", label: "All Cases", icon: ClipboardCheck },
    { to: "/senior/audit", label: "Audit Trail", icon: ScrollText },
    { to: "/senior/notifications", label: "Notifications", icon: Bell },
  ],
  admin: [
    { to: "/admin", label: "Overall Dashboard", icon: LayoutDashboard, end: true },
    { to: "/admin/cases", label: "All Cases", icon: FileCheck2 },
    { to: "/admin/users", label: "Institutions & Users", icon: Users },
    { to: "/admin/policies", label: "Policy Management", icon: Settings2 },
    { to: "/admin/reports", label: "Reports", icon: BarChart3 },
    { to: "/admin/audit", label: "Audit Logs", icon: ScrollText },
    { to: "/admin/notifications", label: "Notifications", icon: Bell },
  ],
};

export function useUnreadCount() {
  const [n, setN] = useState(0);
  const location = useLocation();
  useEffect(() => {
    let alive = true;
    const load = () => api.get("/notifications/unread-count").then((r) => alive && setN(r.data.unread)).catch(() => {});
    load();
    const t = setInterval(load, 20000);
    window.addEventListener("notifications-changed", load);
    return () => {
      alive = false;
      clearInterval(t);
      window.removeEventListener("notifications-changed", load);
    };
  }, [location.pathname]);
  return n;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  if (!user) return null;
  const items = NAV[user.role];

  const doLogout = async () => {
    await logout();
    navigate("/login");
  };

  const sidebar = (
    <div className="flex h-full flex-col bg-gradient-to-b from-navy-900 to-navy-950 text-navy-100">
      <div className="px-5 py-5"><Logo light /></div>
      <div className="mx-4 mb-4 rounded-lg bg-white/5 px-3 py-2.5 text-xs">
        <div className="font-semibold text-white">{user.full_name}</div>
        <div className="text-navy-300">{ROLE_LABEL[user.role]}</div>
        {user.institution_name && <div className="mt-1 flex items-center gap-1 text-teal-300"><Building2 className="h-3 w-3" />{user.institution_name}</div>}
      </div>
      <nav className="flex-1 space-y-0.5 px-3">
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} end={it.end}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? "bg-teal-500/15 text-white ring-1 ring-inset ring-teal-400/30" : "text-navy-200 hover:bg-white/5 hover:text-white"}`}>
            <it.icon className="h-4 w-4" />
            <span className="flex-1">{it.label}</span>
            {it.label === "Notifications" && unread > 0 && (
              <span className="rounded-full bg-teal-500 px-1.5 text-[10px] font-bold text-white">{unread}</span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-2 p-4">
        <button onClick={doLogout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-navy-200 hover:bg-white/5 hover:text-white">
          <LogOut className="h-4 w-4" /> Sign out
        </button>
        <div className="rounded-lg border border-white/10 p-2.5 text-[10px] leading-relaxed text-navy-300">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="flex items-center gap-1 font-semibold uppercase tracking-wider text-navy-200"><ShieldCheck className="h-3.5 w-3.5 text-teal-400" />Built by</span>
            <TeamLogo badge className="h-4" />
          </div>
          SIH 2026 demonstration prototype by Team Lynxcode. Not an official AICTE service. All data is fictional; bank verification is simulated.
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-navy-950/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72">{sidebar}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:px-8">
          <button className="rounded p-1.5 hover:bg-slate-100 lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="lg:hidden"><Logo subtitle={false} /></div>
          <div className="hidden items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200 md:flex">
            Demonstration prototype · fictional data · simulated bank verification
          </div>
          <div className="ml-auto flex items-center gap-2">
            <EvidencePanel />
            <button onClick={() => navigate(`/${user.role}/notifications`)} className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100" aria-label="Notifications">
              <Bell className="h-5 w-5" />
              {unread > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{unread > 99 ? "99+" : unread}</span>}
            </button>
            <div className="hidden text-right text-xs sm:block">
              <div className="font-semibold text-navy-900">{user.full_name}</div>
              <div className="text-slate-500">{ROLE_LABEL[user.role]}</div>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
