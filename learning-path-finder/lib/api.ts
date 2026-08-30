export type Profile = { goal_text: string; role: string | null; goal_skills: string[]; known_skills: string[]; weekly_hours: number; horizon_weeks: number; level: number; style: "balanced" | "project first" | "theory first" };
export type Module = { skill: string; name: string; resource: { id: string; title: string; provider: string; url: string; hours: number } | null };
export type PathData = { profile: Profile; path: { total_weeks: number; feasible: boolean; phases: { title: string; modules: Module[]; weeks: [number, number]; hours: number }[] }; progress: { skills_done: number; skills_total: number; percent: number; hours_done: number; hours_total: number; weeks_left: number | null; current_phase: string | null; next_action: Module | null }; state: { completed: string[]; blocked: string[] } };
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const defaultProfile: Profile = { goal_text: "", role: null, goal_skills: [], known_skills: [], weekly_hours: 5, horizon_weeks: 24, level: 2, style: "balanced" };
// fetch rejects rather than resolving when the server is not running, so the raw browser error
// ("Failed to fetch") reached the screen. Everything goes through here so both cases read the same.
async function post(endpoint: string, body: object) {
  let response: Response;
  try { response = await fetch(`${API}${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch { throw new Error("Cannot reach the learning engine. Is the API running on port 8000?"); }
  if (!response.ok) {
    // FastAPI answers a validation failure with a list of objects, and new Error(list) reads as
    // "[object Object]" on screen.
    const detail = (await response.json().catch(() => null))?.detail;
    const text = Array.isArray(detail) ? detail.map((item) => item?.msg).filter(Boolean).join(", ") : detail;
    throw new Error(text || "The learning engine could not build that path.");
  }
  return response.json();
}
const request = (endpoint: string, body: object): Promise<PathData> => post(endpoint, body);
export const generatePath = (profile = defaultProfile, completed: string[] = [], blocked: string[] = []) => request("/path", { profile, completed, blocked });
export type FeedbackEvent = "completed" | "already_know" | "too_hard" | "too_easy" | "not_interested";
export const sendFeedback = (profile: Profile, completed: string[], blocked: string[], event: FeedbackEvent, skill?: string, resource_id?: string) => request("/path/feedback", { profile, completed, blocked, event, skill, resource_id });
export const completeModule = (profile: Profile, completed: string[], blocked: string[], skill: string) => sendFeedback(profile, completed, blocked, "completed", skill);
export const explainCurrent = (profile: Profile, completed: string[], blocked: string[]): Promise<{ reason: string }> => post("/explain", { profile, completed, blocked });
export type ChatResponse = { reply: string; data?: PathData; profile?: Partial<Profile> };
export type Turn = { role: "assistant" | "user"; content: string };
export const chat = (message: string, profile: Profile | null, completed: string[], blocked: string[], history: Turn[] = []): Promise<ChatResponse> => post("/chat", { message, profile, completed, blocked, history });
