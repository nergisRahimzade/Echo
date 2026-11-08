/**
 * Light / dark theme. Until the user picks one in Settings, Echo follows the device setting.
 * The choice is stored in localStorage and applied as <html data-theme="light|dark">
 * (globals.css reads it); THEME_SCRIPT applies it before the first paint, so there is no flash.
 */

export type Theme = "light" | "dark";
export const THEME_KEY = "echo.theme";

/** Runs in <head> before the page draws. Plain ES5 on purpose, wrapped so blocked storage can't break it. */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

/** The theme on screen now: the saved choice, otherwise the device setting. */
export function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* storage blocked: the theme lasts until the page reloads */
  }
}
