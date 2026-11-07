/**
 * Echo's voice: say a sentence out loud.
 *
 * 1. Natural voice from the server (/tts, ElevenLabs), cached in memory per sentence.
 * 2. If the server has no voice (503) or is unreachable: the browser's built-in voice.
 * `privately` = low volume for the user only (the check flow); otherwise full volume for the listener.
 */

import { tts, type Language } from "@/lib/api";
import { speak, stopSpeaking } from "@/lib/speech";

export interface SayOptions {
  privately?: boolean;
}

const PRIVATE_VOLUME = 0.35;
const audioCache = new Map<string, string>(); // "lang|text" -> object URL
let serverVoice: boolean | null = null; // null = not tried yet
let current: HTMLAudioElement | null = null;

function playUrl(url: string, volume: number): Promise<void> {
  return new Promise((resolve) => {
    current?.pause();
    stopSpeaking();
    const audio = new Audio(url);
    audio.volume = volume;
    current = audio;
    audio.onended = () => resolve();
    audio.onerror = () => resolve();
    audio.play().catch(() => resolve());
  });
}

async function serverAudio(text: string, language: Language): Promise<string | null> {
  const key = `${language}|${text}`;
  const cached = audioCache.get(key);
  if (cached) return cached;
  if (serverVoice === false) return null;
  try {
    const blob = await tts(text, language);
    serverVoice = true;
    const url = URL.createObjectURL(blob);
    audioCache.set(key, url);
    return url;
  } catch {
    serverVoice = false; // no ElevenLabs key (or offline): stop asking, use the browser voice
    return null;
  }
}

export async function sayAloud(text: string, language: Language, opts: SayOptions = {}): Promise<void> {
  if (!text.trim()) return;
  const volume = opts.privately ? PRIVATE_VOLUME : 1;
  const url = await serverAudio(text, language);
  if (url) return playUrl(url, volume);
  await speak(text, language, { volume, rate: 0.95 });
}

/** Play a pre-recorded file if it exists (e.g. /prompts/tr/sayAgain.mp3); false if it doesn't. */
const fileExists = new Map<string, boolean>();
export async function playFile(path: string, opts: SayOptions = {}): Promise<boolean> {
  if (fileExists.get(path) === false) return false;
  if (!fileExists.has(path)) {
    try {
      const res = await fetch(path, { method: "HEAD" });
      fileExists.set(path, res.ok);
    } catch {
      fileExists.set(path, false);
    }
  }
  if (!fileExists.get(path)) return false;
  await playUrl(path, opts.privately ? PRIVATE_VOLUME : 1);
  return true;
}
