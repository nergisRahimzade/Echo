/**
 * Typed client for the Echo backend. One function per endpoint in the API contract
 * (docs/Echo-Build-Tasks.md). Every screen talks to the server only through this file.
 */

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// ---------- Shared types ----------

export type Language = "tr" | "en";
/** What the frontend should do with a translation result. */
export type TranslateAction = "speak" | "check";
/** What to show after feedback: speak it, ask to repeat, call a helper, or nothing. */
export type NextAction = "speak" | "repeat" | "helper" | "done";
export type Verdict = "up" | "down";

export interface Health {
  status: "ok";
  db: "connected" | "disconnected" | "not configured";
}

export interface Phrase {
  id: string;
  text: string;
  category: "greetings" | "needs" | "feelings" | "questions" | "yes_no";
  icon: string;
}

export type WordKind = "person" | "place" | "pet" | "other";

export interface PersonalWord {
  word: string;
  kind: WordKind;
}

export interface TranslateResult {
  utterance_id: string;
  sentence: string;
  score: number;
  action: TranslateAction;
  language: Language;
}

export interface FeedbackResult {
  ok: boolean;
  next_action: NextAction;
}

// ---------- Low-level helpers ----------

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the Echo server.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** File name with an extension that matches the recording's real format. */
function audioFileName(audio: Blob): string {
  if (audio.type.includes("mp4")) return "audio.mp4";
  if (audio.type.includes("ogg")) return "audio.ogg";
  if (audio.type.includes("wav")) return "audio.wav";
  return "audio.webm";
}

// ---------- Endpoints ----------

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export interface User {
  user_id: string;
  name: string;
  main_language: Language | "both";
  threshold: number;
  created_at: string;
}

/** Sign up. `mainLanguage` "both" = the user mixes Turkish and English. */
export function createUser(
  name: string,
  mainLanguage: Language | "both",
  consent: boolean,
): Promise<{ user_id: string }> {
  return postJson("/users", { name, main_language: mainLanguage, consent });
}

export function getUser(userId: string): Promise<User> {
  return request<User>(`/users/${encodeURIComponent(userId)}`);
}

export function getPhrases(lang: Language): Promise<Phrase[]> {
  return request<Phrase[]>(`/phrases?lang=${lang}`);
}

export function enroll(params: {
  userId: string;
  phraseText: string;
  phraseId?: string;
  language?: Language;
  audio: Blob;
}): Promise<{ sample_id: string }> {
  const form = new FormData();
  form.append("user_id", params.userId);
  form.append("phrase_text", params.phraseText);
  if (params.phraseId) form.append("phrase_id", params.phraseId);
  if (params.language) form.append("language", params.language);
  form.append("audio", params.audio, audioFileName(params.audio));
  return request("/enroll", { method: "POST", body: form });
}

export function addWords(userId: string, words: PersonalWord[]): Promise<{ ok: boolean }> {
  return postJson("/words", { user_id: userId, words });
}

export function getWords(userId: string): Promise<PersonalWord[]> {
  return request<PersonalWord[]>(`/words?user_id=${encodeURIComponent(userId)}`);
}

export function deleteWord(userId: string, word: string): Promise<{ ok: boolean }> {
  return request(`/words?user_id=${encodeURIComponent(userId)}&word=${encodeURIComponent(word)}`, {
    method: "DELETE",
  });
}

export function translate(params: {
  userId: string;
  sessionId: string;
  audio: Blob;
}): Promise<TranslateResult> {
  const form = new FormData();
  form.append("user_id", params.userId);
  form.append("session_id", params.sessionId);
  form.append("audio", params.audio, audioFileName(params.audio));
  return request("/translate", { method: "POST", body: form });
}

export function sendFeedback(params: {
  utteranceId: string;
  verdict: Verdict;
  finalText?: string;
}): Promise<FeedbackResult> {
  return postJson("/feedback", {
    utterance_id: params.utteranceId,
    verdict: params.verdict,
    final_text: params.finalText,
  });
}

/** Returns mp3 audio for the sentence. */
export async function tts(text: string, language: Language): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the Echo server.");
  }
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return res.blob();
}

export function deleteUserData(userId: string): Promise<{ ok: boolean }> {
  return request(`/users/${encodeURIComponent(userId)}/data`, { method: "DELETE" });
}
