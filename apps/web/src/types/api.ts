export interface DocumentSummary {
  document_id: string;
  title: string;
  source_filename: string;
  document_version: string | null;
  academic_year: string | null;
  authenticity_verified: boolean;
  page_count: number;
  chunk_count: number;
  sha256: string;
  ingested_at: string;
  headings: string[];
  ocr_page_count: number;
  empty_page_count: number;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
  authenticity_notice: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_title: string;
  document_version: string | null;
  source_filename: string;
  page_number: number;
  excerpt: string;
  distance: number;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  insufficient_evidence: boolean;
  limitation: string | null;
  conversation_id: string;
  retrieved_chunk_count: number;
}

export interface HealthResponse {
  status: string;
  service: string;
  embedding_provider: string;
  generation_provider: string;
  documents_indexed: number;
  groq_configured: boolean;
  groq_model: string;
  embedding_model: string;
}

export interface ApiError {
  code: string;
  message: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  citations?: Citation[];
  insufficient_evidence?: boolean;
  limitation?: string | null;
  pending?: boolean;
  error?: string | null;
}
