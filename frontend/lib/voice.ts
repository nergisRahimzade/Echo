/**
 * Echo's voice: say a sentence out loud.
 * `privately` = low volume for the user only (the check flow), otherwise full volume for the listener.
 */

import type { Language } from "@/lib/api";
import { speak } from "@/lib/speech";

export interface SayOptions {
  privately?: boolean;
}

export async function sayAloud(text: string, language: Language, opts: SayOptions = {}): Promise<void> {
  if (!text.trim()) return;
  await speak(text, language, { volume: opts.privately ? 0.35 : 1, rate: 0.95 });
}
