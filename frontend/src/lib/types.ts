// ── Shared TypeScript types matching backend schemas ──────────────────────────

export interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface KnowledgeSpace {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessingEstimate {
  estimated_seconds: number;
  estimated_label: string;
  model_used: string;
  is_long_content: boolean;
  warning: string | null;
}

export interface SourcePreview {
  url: string;
  canonical_url: string | null;
  source_type: "youtube" | "podcast" | "audio";
  title: string | null;
  creator_name: string | null;
  thumbnail_url: string | null;
  duration_sec: number | null;
  duration_label: string | null;
  publish_date: string | null;
  language: string | null;
  processing_estimate: ProcessingEstimate | null;
  error: string | null;
}

export interface Source {
  id: string;
  source_type: string;
  source_url: string;
  canonical_url: string | null;
  title: string | null;
  creator_name: string | null;
  thumbnail_url: string | null;
  duration_sec: number | null;
  language: string;
  status: string;
  transcript_status: string;
  indexing_status: string;
  audio_storage_policy: string;
  created_at: string;
  updated_at: string;
}

export interface SourceIngestResponse {
  source: Source;
  job_id: string;
  job_status: string;
}

export interface Job {
  id: string;
  source_id: string | null;
  job_type: string;
  status: string;
  stage: string | null;
  progress: number;
  current_step: string | null;
  estimated_seconds_remaining: number | null;
  heartbeat_at: string | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  is_retryable: boolean;
}

export interface TranscriptSegment {
  id: string;
  segment_index: number;
  start_time_sec: string;
  end_time_sec: string;
  text: string;
  speaker_label: string | null;
  confidence_score: string | null;
}

export interface TranscriptPage {
  segments: TranscriptSegment[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

export interface EvidenceHit {
  chunk_id: string;
  source_id: string;
  space_id: string | null;
  source_title: string | null;
  start_time_sec: string;
  end_time_sec: string;
  excerpt: string;
  score: number;
  confidence_label: "High" | "Medium" | "Low" | string;
  navigation_url: string | null;
}

export interface AskQuestionResponse {
  answer: string;
  evidence: EvidenceHit[];
  insufficient_evidence: boolean;
}

export interface ChatSession {
  id: string;
  user_id: string;
  space_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatEvidence {
  id: string;
  message_id: string;
  user_id: string;
  source_id: string | null;
  chunk_id: string | null;
  claim_text: string | null;
  excerpt: string;
  source_title: string | null;
  start_time_sec: string;
  end_time_sec: string;
  relevance_score: string | null;
  confidence_label: "High" | "Medium" | "Low" | "Insufficient";
  created_at: string;
  navigation_url: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  user_id: string;
  role: string;
  content: string;
  sequence_number: number;
  created_at: string;
  evidence: ChatEvidence[];
}

// ── API error shape from FastAPI ───────────────────────────────────────────────
export interface ApiError {
  detail: string | { msg: string; type: string }[];
}

export function getErrorMessage(error: unknown): string {
  if (!error || typeof error !== "object") return "An unexpected error occurred";
  const err = error as { response?: { data?: ApiError } };
  const detail = err.response?.data?.detail;
  if (!detail) return "An unexpected error occurred";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
  return "An unexpected error occurred";
}
