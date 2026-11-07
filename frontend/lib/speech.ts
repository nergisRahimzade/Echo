/**
 * Read text aloud with the browser's built-in voice (Web Speech API).
 * Used for prompts and as the fallback when the /tts endpoint is unavailable.
 */

import type { Language } from "@/lib/api";

const VOICE_LANG: Record<Language, string> = { tr: "tr-TR", en: "en-US" };

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string, language: Language, opts: { rate?: number; volume?: number } = {}): Promise<void> {
  return new Promise((resolve) => {
    if (!canSpeak()) return resolve();
    const synth = window.speechSynthesis;
    synth.cancel(); // never talk over ourselves
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = VOICE_LANG[language];
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(language));
    if (voice) utterance.voice = voice;
    utterance.rate = opts.rate ?? 0.9; // a little slower is easier to follow
    utterance.volume = opts.volume ?? 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    synth.speak(utterance);
  });
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}
