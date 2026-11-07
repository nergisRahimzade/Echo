/**
 * Short spoken prompts Echo says to the user (never shown as text).
 * Each language needs one entry per prompt; adding a language = adding its lines here.
 */

import type { Language } from "@/lib/api";
import { playFile, sayAloud } from "@/lib/voice";

export type PromptId = "sayAgain" | "helper";

export const PROMPTS: Record<Language, Record<PromptId, string>> = {
  tr: {
    sayAgain: "Lütfen tekrar söyle.",
    helper: "Bir yardımcı yazabilir.",
  },
  en: {
    sayAgain: "Please say it again.",
    helper: "A helper can type it.",
  },
};

/**
 * Say a prompt to the user (quietly: it's for them, not the listener).
 * Uses the pre-recorded file from backend/scripts/make_prompts.py when present.
 */
export async function playPrompt(id: PromptId, language: Language): Promise<void> {
  const played = await playFile(`/prompts/${language}/${id}.mp3`, { privately: true });
  if (!played) await sayAloud(PROMPTS[language][id], language, { privately: true });
}
