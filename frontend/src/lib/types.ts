export type Role = "institution" | "officer" | "senior" | "admin";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  institution_id: number | null;
  institution_name: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface ValidationSummary { errors: number; warnings: number; info: number; passed: number }

export interface FDR {
  id: number;
  reference_no: string;
  institution_id: number;
  institution_name: string;
  fdr_number: string | null;
  bank_name: string | null;
  branch_name: string | null;
  account_holder: string | null;
  account_number_masked: string | null;
  principal_amount: number | null;
  interest_rate: number | null;
  issue_date: string | null;
  maturity_date: string | null;
  days_to_maturity: number | null;
  purpose: string;
  submission_status: string;
  document_status: string;
  bank_status: string;
  is_cleared: boolean;
  stage: string;
  clearance_status: string | null;
  assigned_officer: string | null;
  assigned_officer_id: number | null;
  submitted_at: string | null;
  review_due_at: string | null;
  last_review_remarks: string | null;
  created_at: string;
  updated_at: string;
  validation?: ValidationSummary;
}

export interface DocumentInfo {
  id: number;
  doc_type: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  uploaded_by: string | null;
  uploaded_at: string;
  ocr_status: string;
  ocr_engine: string | null;
  ocr_mean_confidence: number | null;
  ocr_message: string | null;
  ocr_duration_ms: number | null;
}

export interface ExtractedField {
  id: number;
  document_id: number;
  field_name: string;
  label: string;
  extracted_value: string | null;
  confidence: number | null;
  needs_review: boolean;
  confirmed_value: string | null;
  is_confirmed: boolean;
  was_corrected: boolean;
}

export interface ValidationItem {
  check_code: string;
  severity: "error" | "warning" | "info" | "pass";
  message: string;
  field_name: string | null;
  created_at?: string;
}

export interface Verification {
  id: number;
  outcome: string;
  adapter: string;
  is_simulated: boolean;
  reference: string;
  remarks: string;
  response_summary: string;
  evidence_document_id: number | null;
  officer: string | null;
  created_at: string;
}

export interface Decision {
  id: number;
  decision: string;
  remarks: string;
  decided_by: string | null;
  decided_by_id: number;
  created_at: string;
}

export interface Clearance {
  id: number;
  fdr_id: number;
  status: string;
  reason: string;
  requested_by: string | null;
  created_at: string;
  prerequisite_snapshot: Eligibility;
  recommendation: string | null;
  recommendation_remarks: string | null;
  recommended_by: string | null;
  recommended_by_id: number | null;
  recommended_at: string | null;
  decided_at: string | null;
  decisions: Decision[];
  fdr?: FDR;
  current_eligibility?: Eligibility;
}

export interface Eligibility {
  eligible: boolean;
  checks: { code: string; label: string; ok: boolean }[];
}

export interface AuditEntry {
  id: number;
  created_at: string;
  user_id: number | null;
  user_email: string | null;
  role: string | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  fdr_id: number | null;
  previous_status: string | null;
  new_status: string | null;
  description: string;
  details: Record<string, unknown>;
  reference_no?: string | null;
}

export interface FDRDetail extends FDR {
  documents: DocumentInfo[];
  receipt_document_id: number | null;
  ocr_text: string | null;
  extracted_fields: ExtractedField[];
  validation_results: ValidationItem[];
  bank_verifications: Verification[];
  clearance_requests: Clearance[];
  eligibility: Eligibility;
  required_documents: string[];
  audit: AuditEntry[];
}

export interface Notification {
  id: number;
  kind: string;
  severity: "info" | "warning" | "critical" | "success";
  title: string;
  message: string;
  link: string | null;
  fdr_id: number | null;
  is_read: boolean;
  created_at: string;
}
