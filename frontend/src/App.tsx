import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { ROLE_HOME } from "./lib/format";
import type { Role } from "./lib/types";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import Dashboard from "./pages/shared/Dashboard";
import CaseList from "./pages/shared/CaseList";
import CaseDetail from "./pages/shared/CaseDetail";
import ClearanceList from "./pages/shared/ClearanceList";
import ClearanceDetail from "./pages/shared/ClearanceDetail";
import Notifications from "./pages/shared/Notifications";
import UploadFdr from "./pages/institution/UploadFdr";
import OcrReview from "./pages/officer/OcrReview";
import BankQueue from "./pages/officer/BankQueue";
import UsersInstitutions from "./pages/admin/UsersInstitutions";
import Policies from "./pages/admin/Policies";
import Reports from "./pages/admin/Reports";
import AuditLogs from "./pages/admin/AuditLogs";

/** Frontend guard for navigation only - every API endpoint enforces the same rules on the server. */
function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return <>{children}</>;
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return <Navigate to={user ? ROLE_HOME[user.role] : "/login"} replace />;
}

const area = (role: Role, children: ReactNode) => (
  <Route path={`/${role}`} element={<RequireRole role={role}><Layout /></RequireRole>}>{children}</Route>
);

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Home />} />

      {area("institution", <>
        <Route index element={<Dashboard />} />
        <Route path="fdrs" element={<CaseList />} />
        <Route path="fdrs/:id" element={<CaseDetail />} />
        <Route path="upload" element={<UploadFdr />} />
        <Route path="upload/:id" element={<UploadFdr />} />
        <Route path="clearances" element={<ClearanceList />} />
        <Route path="notifications" element={<Notifications />} />
      </>)}

      {area("officer", <>
        <Route index element={<Dashboard />} />
        <Route path="cases" element={<CaseList />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="cases/:id/ocr" element={<OcrReview />} />
        <Route path="bank" element={<BankQueue />} />
        <Route path="clearances" element={<ClearanceList />} />
        <Route path="clearances/:id" element={<ClearanceDetail />} />
        <Route path="reports" element={<Reports />} />
        <Route path="notifications" element={<Notifications />} />
      </>)}

      {area("senior", <>
        <Route index element={<Dashboard />} />
        <Route path="approvals" element={<ClearanceList />} />
        <Route path="decisions/:id" element={<ClearanceDetail />} />
        <Route path="cases" element={<CaseList />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="cases/:id/ocr" element={<OcrReview />} />
        <Route path="audit" element={<AuditLogs />} />
        <Route path="notifications" element={<Notifications />} />
      </>)}

      {area("admin", <>
        <Route index element={<Dashboard />} />
        <Route path="cases" element={<CaseList />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="users" element={<UsersInstitutions />} />
        <Route path="policies" element={<Policies />} />
        <Route path="reports" element={<Reports />} />
        <Route path="audit" element={<AuditLogs />} />
        <Route path="notifications" element={<Notifications />} />
      </>)}

      <Route path="*" element={<Home />} />
    </Routes>
  );
}
