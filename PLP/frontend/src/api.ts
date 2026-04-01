import type {
  AdminCandidateDetail,
  AdminCandidateListResponse,
  CandidateSessionDetail,
  ModuleSummary,
  StartSessionResponse,
  UserProfile
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include"
  });
  return parseResponse<T>(response);
}

export const api = {
  health: () => apiRequest<{ status: string; service: string }>("/health"),
  modules: () => apiRequest<ModuleSummary[]>("/modules"),
  session: () => apiRequest<UserProfile>("/auth/session"),
  me: () => apiRequest<UserProfile>("/auth/me"),
  logout: () =>
    apiRequest<{ message: string }>("/auth/logout", {
      method: "POST"
    }),
  authLoginUrl: (provider: "google" | "microsoft", nextPath = "/dashboard") =>
    `${API_BASE_URL}/auth/auth0/login?provider=${encodeURIComponent(provider)}&next=${encodeURIComponent(nextPath)}`,
  startSession: (moduleSlug: string) =>
    apiRequest<StartSessionResponse>(
      "/candidate/sessions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ module_slug: moduleSlug })
      }
    ),
  sessionDetail: (sessionId: string) => apiRequest<CandidateSessionDetail>(`/candidate/sessions/${sessionId}`),
  uploadAnswer: async (sessionId: string, questionId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<{ answer_id: string; status: string; audio_url: string }>(
      `/candidate/sessions/${sessionId}/answers/${questionId}/audio`,
      {
        method: "POST",
        body: formData
      }
    );
  },
  submitSession: (sessionId: string) =>
    apiRequest<{ session_id: string; status: string; message: string }>(
      `/candidate/sessions/${sessionId}/submit`,
      { method: "POST" }
    ),
  adminList: () => apiRequest<AdminCandidateListResponse>("/admin/candidates"),
  adminDetail: (sessionId: string) => apiRequest<AdminCandidateDetail>(`/admin/candidates/${sessionId}`),
  setManualScore: (sessionId: string, manualScore: number, notes: string) =>
    apiRequest(
      `/admin/candidates/${sessionId}/manual-score`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ manual_score: manualScore, notes })
      }
    ),
  deleteCandidate: async (sessionId: string) => {
    const response = await fetch(`${API_BASE_URL}/admin/candidates/${sessionId}`, {
      method: "DELETE",
      credentials: "include"
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Delete failed");
    }
  }
};
