"use client";

/**
 * Interface languages. Every visible text, screen-reader label and spoken prompt lives in
 * frontend/locales/<code>.json. To add a language: add its JSON file (same keys as en.json)
 * and one line to UI_LANGUAGES below.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import en from "@/locales/en.json";
import tr from "@/locales/tr.json";
import type { FlagCode } from "@/components/Flag";

export const UI_LANGUAGES = [
  { code: "tr", name: "Türkçe", flag: "tr", dict: tr },
  { code: "en", name: "English", flag: "gb", dict: en },
] as const satisfies readonly { code: string; name: string; flag: FlagCode; dict: unknown }[];

export type UiLang = (typeof UI_LANGUAGES)[number]["code"];
export type Vars = Record<string, string | number>;

const KEY = "echo.uiLang";
const FALLBACK: UiLang = "en";

function dictFor(lang: string): Record<string, unknown> {
  return (UI_LANGUAGES.find((l) => l.code === lang)?.dict ?? en) as Record<string, unknown>;
}

function lookup(dict: Record<string, unknown>, key: string): string | undefined {
  let node: unknown = dict;
  for (const part of key.split(".")) {
    if (node && typeof node === "object" && part in node) node = (node as Record<string, unknown>)[part];
    else return undefined;
  }
  return typeof node === "string" ? node : undefined;
}

/** Translate outside React (e.g. spoken prompts in a given language). Falls back to English, then the key. */
export function translate(lang: string, key: string, vars?: Vars): string {
  const text = lookup(dictFor(lang), key) ?? lookup(dictFor(FALLBACK), key) ?? key;
  return vars ? text.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? `{${name}}`)) : text;
}

export function isUiLang(value: unknown): value is UiLang {
  return UI_LANGUAGES.some((l) => l.code === value);
}

/** The starting language: the saved choice, else the user's main language, else the browser's. */
function initialLang(): UiLang {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (isUiLang(saved)) return saved;
    const user = JSON.parse(window.localStorage.getItem("echo.user") ?? "null");
    if (user?.main_language === "both") return "tr";
    if (isUiLang(user?.main_language)) return user.main_language;
  } catch {
    /* storage blocked */
  }
  const browser = typeof navigator !== "undefined" ? navigator.language.slice(0, 2) : "";
  return isUiLang(browser) ? browser : FALLBACK;
}

interface I18n {
  lang: UiLang;
  setLang: (lang: UiLang, remember?: boolean) => void;
  t: (key: string, vars?: Vars) => string;
}

const I18nContext = createContext<I18n>({ lang: FALLBACK, setLang: () => {}, t: (k, v) => translate(FALLBACK, k, v) });

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<UiLang>(FALLBACK);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is only readable after mount
  useEffect(() => setLangState(initialLang()), []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: UiLang, remember = true) => {
    setLangState(next);
    if (!remember) return;
    try {
      window.localStorage.setItem(KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<I18n>(() => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  return useContext(I18nContext);
}

/** Shortcut: `const t = useT(); t("talk.yes")`. */
export function useT() {
  return useContext(I18nContext).t;
}


/** An error to show: the server's own message, or one of ours by key (translated when shown). */
export type UiError = { text: string } | { key: string };

export function toUiError(err: unknown, fallbackKey: string): UiError {
  if (err instanceof Error && err.name === "ApiError" && err.message) return { text: err.message };
  return { key: fallbackKey };
}

export function showError(error: UiError, t: (key: string, vars?: Vars) => string): string {
  return "text" in error ? error.text : t(error.key);
}
