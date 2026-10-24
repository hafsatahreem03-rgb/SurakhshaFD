import { useState } from "react";
import { Building2, Loader2, Plus, UserPlus } from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { useFetch } from "../../lib/useFetch";
import { ROLE_LABEL, fmtDateTime, inr } from "../../lib/format";
import type { Role, User } from "../../lib/types";
import { Badge, Card, ErrorState, Field, Modal, PageHeader, Spinner, Table, useToast } from "../../components/ui";

interface Inst { id: number; name: string; code: string; city: string; state: string; contact_email: string; fdr_count: number; total_amount: number; user_count: number }

export default function UsersInstitutions() {
  const toast = useToast();
  const users = useFetch<User[]>("/admin/users");
  const insts = useFetch<Inst[]>("/institutions");
  const [userModal, setUserModal] = useState(false);
  const [instModal, setInstModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [u, setU] = useState({ email: "", full_name: "", password: "", role: "institution" as Role, institution_id: "" });
  const [i, setI] = useState({ name: "", code: "", city: "", state: "", contact_email: "" });

  const createUser = async () => {
    setBusy(true);
    try {
      await api.post("/admin/users", { ...u, institution_id: u.role === "institution" ? Number(u.institution_id) || null : null });
      toast("success", `User ${u.email} created.`);
      setUserModal(false);
      setU({ email: "", full_name: "", password: "", role: "institution", institution_id: "" });
      users.reload();
      insts.reload();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const createInst = async () => {
    setBusy(true);
    try {
      await api.post("/institutions", i);
      toast("success", `Institution ${i.name} created.`);
      setInstModal(false);
      setI({ name: "", code: "", city: "", state: "", contact_email: "" });
      insts.reload();
    } catch (e) {
      toast("error", errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (x: User) => {
    try {
      await api.patch(`/admin/users/${x.id}`, { is_active: !x.is_active });
      toast("success", `${x.email} ${x.is_active ? "deactivated" : "activated"}.`);
      users.reload();
    } catch (e) {
      toast("error", errorMessage(e));
    }
  };

  return (
    <div>
      <PageHeader title="Institutions & Users" subtitle="Manage demo institutions and accounts. Passwords are stored only as bcrypt hashes."
        actions={<>
          <button className="btn-outline" onClick={() => setInstModal(true)}><Building2 className="h-4 w-4" />Add institution</button>
          <button className="btn-primary" onClick={() => setUserModal(true)}><UserPlus className="h-4 w-4" />Add user</button>
        </>} />

      <Card title="Institutions (fictional)" bodyClass="p-0" className="mb-6">
        {insts.loading ? <Spinner /> : insts.error ? <div className="p-5"><ErrorState message={insts.error} /></div> : (
          <Table head={["Institution", "Code", "Location", "Users", "FDRs", "Total deposits"]}>
            {insts.data?.map((x) => (
              <tr key={x.id}>
                <td className="td font-medium">{x.name}<div className="text-xs text-slate-500">{x.contact_email}</div></td>
                <td className="td font-mono text-xs">{x.code}</td>
                <td className="td text-slate-600">{[x.city, x.state].filter(Boolean).join(", ")}</td>
                <td className="td">{x.user_count}</td>
                <td className="td">{x.fdr_count}</td>
                <td className="td font-semibold">{inr(x.total_amount)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card title="User accounts" bodyClass="p-0">
        {users.loading ? <Spinner /> : users.error ? <div className="p-5"><ErrorState message={users.error} /></div> : (
          <Table head={["User", "Role", "Institution", "Last login", "Status", ""]}>
            {users.data?.map((x) => (
              <tr key={x.id}>
                <td className="td"><div className="font-medium">{x.full_name}</div><div className="text-xs text-slate-500">{x.email}</div></td>
                <td className="td"><Badge tone={x.role === "admin" ? "navy" : x.role === "senior" ? "purple" : x.role === "officer" ? "teal" : "blue"}>{ROLE_LABEL[x.role]}</Badge></td>
                <td className="td text-sm text-slate-600">{x.institution_name || "—"}</td>
                <td className="td text-xs text-slate-500">{fmtDateTime(x.last_login_at)}</td>
                <td className="td">{x.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Deactivated</Badge>}</td>
                <td className="td text-right"><button className="btn-outline btn-sm" onClick={() => toggleActive(x)}>{x.is_active ? "Deactivate" : "Activate"}</button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Modal open={userModal} title="Add user" onClose={() => setUserModal(false)}
        footer={<><button className="btn-outline" onClick={() => setUserModal(false)}>Cancel</button>
          <button className="btn-primary" disabled={busy} onClick={createUser}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}Create user</button></>}>
        <div className="grid gap-3">
          <Field label="Full name"><input className="input" value={u.full_name} onChange={(e) => setU({ ...u, full_name: e.target.value })} /></Field>
          <Field label="Email"><input className="input" type="email" value={u.email} onChange={(e) => setU({ ...u, email: e.target.value })} /></Field>
          <Field label="Initial password" hint="At least 8 characters"><input className="input" type="password" value={u.password} onChange={(e) => setU({ ...u, password: e.target.value })} /></Field>
          <Field label="Role">
            <select className="input" value={u.role} onChange={(e) => setU({ ...u, role: e.target.value as Role })}>
              {(Object.keys(ROLE_LABEL) as Role[]).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
          </Field>
          {u.role === "institution" && (
            <Field label="Institution">
              <select className="input" value={u.institution_id} onChange={(e) => setU({ ...u, institution_id: e.target.value })}>
                <option value="">Select…</option>
                {insts.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </Field>
          )}
        </div>
      </Modal>

      <Modal open={instModal} title="Add institution" onClose={() => setInstModal(false)}
        footer={<><button className="btn-outline" onClick={() => setInstModal(false)}>Cancel</button>
          <button className="btn-primary" disabled={busy} onClick={createInst}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}Create institution</button></>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><Field label="Name"><input className="input" value={i.name} onChange={(e) => setI({ ...i, name: e.target.value })} placeholder="e.g. Kaveri Institute of Design (Demo)" /></Field></div>
          <Field label="Code"><input className="input" value={i.code} onChange={(e) => setI({ ...i, code: e.target.value })} placeholder="DEMO-KID-06" /></Field>
          <Field label="Contact email"><input className="input" value={i.contact_email} onChange={(e) => setI({ ...i, contact_email: e.target.value })} /></Field>
          <Field label="City"><input className="input" value={i.city} onChange={(e) => setI({ ...i, city: e.target.value })} /></Field>
          <Field label="State"><input className="input" value={i.state} onChange={(e) => setI({ ...i, state: e.target.value })} /></Field>
        </div>
      </Modal>
    </div>
  );
}
