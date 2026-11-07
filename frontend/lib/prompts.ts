/**
 * Short spoken prompts Echo says to the user (never shown as text).
 * The words live in frontend/locales/<lang>.json under "prompts".
 */

import type { Language } from "@/lib/api";
import { translate } from "@/lib/i18n";
import { playFile, sayAloud } from "@/lib/voice";

export type PromptId = "sayAgain" | "helper";

/**
 * Say a prompt to the user in `language` (quietly: it's for them, not the listener).
 * Uses the pre-recorded file from backend/scripts/make_prompts.py when present.
 */
export async function playPrompt(id: PromptId, language: Language): Promise<void> {
  const played = await playFile(`/prompts/${language}/${id}.mp3`, { privately: true });
  if (!played) await sayAloud(translate(language, `prompts.${id}`), language, { privately: true });
}
