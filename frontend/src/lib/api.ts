import type {
  ProfileSummary,
  RecommendResponse,
  RegretReport,
  ResolveResponse,
  TasteProfile,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new Error(`${r.status}: ${body || r.statusText}`);
  }
  return r.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const errText = await r.text().catch(() => "");
    throw new Error(`${r.status}: ${errText || r.statusText}`);
  }
  return r.json();
}

export const api = {
  steamLoginUrl: () => `${API_BASE}/api/auth/steam/login`,

  resolveProfile: (input: string) =>
    post<ResolveResponse>("/api/profile/resolve", { input }),

  profileSummary: (steamid: number | string) =>
    get<ProfileSummary>(`/api/profile/${steamid}/summary`),

  tasteProfile: (steamid: number | string) =>
    get<TasteProfile>(`/api/taste/${steamid}/profile`),

  recommendNew: (steamid: number | string, mode = "best_fit", k = 10) =>
    get<RecommendResponse>(`/api/taste/${steamid}/recommend/new?mode=${mode}&k=${k}`),

  recommendOwned: (steamid: number | string, k = 15) =>
    get<RecommendResponse>(`/api/taste/${steamid}/recommend/owned?k=${k}`),

  regret: (steamid: number | string) =>
    get<RegretReport>(`/api/taste/${steamid}/regret`),
};
