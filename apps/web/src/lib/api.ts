import type {
  ChatResponse,
  DocumentListResponse,
  HealthResponse,
  ApiError,
} from "@/types/api";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiRequestError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
  }
}

async function parseError(response: Response): Promise<ApiRequestError> {
  try {
    const body = (await response.json()) as { error?: ApiError };
    const message = body.error?.message ?? "The assistant could not complete that request.";
    const code = body.error?.code ?? "REQUEST_FAILED";
    return new ApiRequestError(message, code, response.status);
  } catch {
    return new ApiRequestError("The assistant could not complete that request.", "REQUEST_FAILED", response.status);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiRequestError(
      "Cannot reach the prospectus API. Start the FastAPI server on port 8000.",
      "NETWORK_ERROR",
      0,
    );
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export function getApiUrl(): string {
  return API_URL;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health");
}

export function fetchDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/api/v1/documents");
}

export function sendChat(payload: {
  question: string;
  conversation_id?: string | null;
  document_ids?: string[];
}): Promise<ChatResponse> {
  return request<ChatResponse>("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function ingestDocument(form: FormData, adminKey: string): Promise<unknown> {
  return request("/api/v1/documents/ingest", {
    method: "POST",
    headers: { "X-Admin-Key": adminKey },
    body: form,
  });
}
