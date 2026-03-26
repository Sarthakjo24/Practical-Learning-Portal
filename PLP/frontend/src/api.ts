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
  options: RequestInit = {},
  accessToken?: string
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  return parseResponse<T>(response);
}

export const api = {
  health: () => apiRequest<{ status: string; service: string }>("/health"),
  modules: () => apiRequest<ModuleSummary[]>("/modules"),
  me: (token: string) => apiRequest<UserProfile>("/auth/me", {}, token),
  startSession: (token: string, moduleSlug: string) =>
    apiRequest<StartSessionResponse>(
      "/candidate/sessions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ module_slug: moduleSlug })
      },
      token
    ),
  sessionDetail: (token: string, sessionId: string) =>
    apiRequest<CandidateSessionDetail>(`/candidate/sessions/${sessionId}`, {}, token),
  uploadAnswer: async (token: string, sessionId: string, questionId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<{ answer_id: string; status: string; audio_url: string }>(
      `/candidate/sessions/${sessionId}/answers/${questionId}/audio`,
      {
        method: "POST",
        body: formData
      },
      token
    );
  },
  submitSession: (token: string, sessionId: string) =>
    apiRequest<{ session_id: string; status: string; message: string }>(
      `/candidate/sessions/${sessionId}/submit`,
      { method: "POST" },
      token
    ),
  adminList: (token: string) => apiRequest<AdminCandidateListResponse>("/admin/candidates", {}, token),
  adminDetail: (token: string, sessionId: string) =>
    apiRequest<AdminCandidateDetail>(`/admin/candidates/${sessionId}`, {}, token),
  setManualScore: (token: string, sessionId: string, manualScore: number, notes: string) =>
    apiRequest(
      `/admin/candidates/${sessionId}/manual-score`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ manual_score: manualScore, notes })
      },
      token
    ),
  deleteCandidate: async (token: string, sessionId: string) => {
    const response = await fetch(`${API_BASE_URL}/admin/candidates/${sessionId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Delete failed");
    }
  }
};
