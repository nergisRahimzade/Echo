/**
 * The signed-up user, remembered in this browser's localStorage so a refresh keeps them.
 * (Storage can be blocked in private mode, so every access is wrapped in try/catch.)
 */

import type { Language } from "@/lib/api";

export type MainLanguage = Language | "both";

export interface SavedUser {
  user_id: string;
  name: string;
  main_language: MainLanguage;
}

const KEY = "echo.user";

export function loadUser(): SavedUser | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SavedUser;
    return parsed?.user_id ? parsed : null;
  } catch {
    return null;
  }
}

export function saveUser(user: SavedUser): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(user));
  } catch {
    /* storage blocked: the user stays signed in until the tab closes */
  }
}

export function clearUser(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** The language to use for speaking prompts: "both" falls back to Turkish first. */
export function speakingLanguage(user: Pick<SavedUser, "main_language"> | null): Language {
  return user?.main_language === "en" ? "en" : "tr";
}
