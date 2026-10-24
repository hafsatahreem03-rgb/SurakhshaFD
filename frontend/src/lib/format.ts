import type { Role } from "./types";

/** ₹ in Indian grouping, e.g. 1000000 -> ₹10,00,000 */
export function inr(v: number | null | undefined, compact = false): string {
  if (v === null || v === undefined || isNaN(v)) return "—";
  if (compact) {
    if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
    if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  }
  return "₹" + Math.round(v).toLocaleString("en-IN");
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s.length === 10 ? s + "T00:00:00" : s + (s.endsWith("Z") ? "" : "Z"));
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s + (s.endsWith("Z") ? "" : "Z")); // API timestamps are UTC
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function timeAgo(s: string): string {
  const diff = (Date.now() - new Date(s + (s.endsWith("Z") ? "" : "Z")).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return `${Math.floor(diff / 86400)} d ago`;
}

export type Tone = "gray" | "blue" | "amber" | "red" | "green" | "teal" | "purple" | "navy";

export const STAGES: Record<string, [string, Tone]> = {
  draft: ["Draft", "gray"],
  submitted: ["Submitted", "blue"],
  under_document_review: ["Under document review", "blue"],
  correction_requested: ["Correction requested", "amber"],
  awaiting_bank_verification: ["Awaiting bank verification", "purple"],
  bank_confirmed_demo: ["Bank confirmed (demo)", "teal"],
  clearance_requested: ["Clearance requested", "amber"],
  awaiting_final_approval: ["Awaiting final approval", "purple"],
  cleared_demo: ["Cleared (demo)", "green"],
  rejected: ["Rejected", "red"],
};

export const DOC_STATUS: Record<string, [string, Tone]> = {
  not_submitted: ["Not submitted", "gray"],
  pending_review: ["Pending review", "blue"],
  discrepancy: ["Discrepancy", "red"],
  correction_requested: ["Correction requested", "amber"],
  document_checked: ["Document checked", "green"],
  rejected: ["Rejected", "red"],
};

export const BANK_STATUS: Record<string, [string, Tone]> = {
  not_started: ["Not started", "gray"],
  pending: ["Pending · simulated", "amber"],
  confirmed: ["Confirmed · simulated", "teal"],
  mismatch: ["Mismatch · simulated", "red"],
  failed: ["Failed · simulated", "red"],
};

export const CLEARANCE_STATUS: Record<string, [string, Tone]> = {
  pending_officer_review: ["Pending officer review", "amber"],
  recommended_approval: ["Recommended: approve", "purple"],
  recommended_rejection: ["Recommended: reject", "purple"],
  approved: ["Approved (demo)", "green"],
  rejected: ["Rejected", "red"],
};

export const DOC_TYPES: Record<string, string> = {
  fdr_receipt: "FDR receipt",
  payment_proof: "Payment proof",
  lien_letter: "Bank lien letter",
  bank_evidence: "Bank evidence",
  other: "Other document",
};

export const ROLE_LABEL: Record<Role, string> = {
  institution: "Institution",
  officer: "AICTE Officer",
  senior: "Senior Approving Officer",
  admin: "Administrator",
};

export const ROLE_HOME: Record<Role, string> = {
  institution: "/institution",
  officer: "/officer",
  senior: "/senior",
  admin: "/admin",
};

export function humanize(s: string | null | undefined): string {
  if (!s) return "—";
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()).replace(/\b(ocr|fdr|noc|csv)\b/gi, (m) => m.toUpperCase());
}

/** Where should a case/clearance link go for this role? (backend links use officer paths) */
export function caseLink(role: Role, fdrId: number): string {
  return role === "institution" ? `/institution/fdrs/${fdrId}` : `/${role === "officer" ? "officer" : role}/cases/${fdrId}`;
}

export function resolveLink(role: Role, link: string | null): string | null {
  if (!link) return null;
  const m = link.match(/^\/(officer|institution)\/(cases|fdrs)\/(\d+)/);
  if (m) return caseLink(role, Number(m[3]));
  const c = link.match(/^\/(officer\/clearances|senior\/decisions)\/(\d+)/);
  if (c) {
    if (role === "senior") return `/senior/decisions/${c[2]}`;
    if (role === "officer") return `/officer/clearances/${c[2]}`;
    if (role === "institution") return "/institution/clearances";
  }
  return link;
}
