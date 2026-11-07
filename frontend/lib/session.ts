/**
 * One conversation = one session id. Kept in sessionStorage so it survives a reload of the
 * tab, and replaced when the user starts a new conversation.
 */

const KEY = "echo.session";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function currentSessionId(): string {
  try {
    const existing = window.sessionStorage.getItem(KEY);
    if (existing) return existing;
    const id = newId();
    window.sessionStorage.setItem(KEY, id);
    return id;
  } catch {
    return newId();
  }
}

export function startNewSession(): string {
  const id = newId();
  try {
    window.sessionStorage.setItem(KEY, id);
  } catch {
    /* ignore */
  }
  return id;
}
