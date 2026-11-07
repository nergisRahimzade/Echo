/**
 * Echo's voice: say a sentence out loud.
 *
 * 1. Natural voice from the server (/tts, ElevenLabs) in the user's chosen voice, cached in memory.
 * 2. If the server has no voice key (503): the browser's built-in voice for the rest of the session.
 *    A one-off failure (bad Wi-Fi, server restarting) only falls back for that one sentence.
 * `privately` = low volume for the user only (the check flow); otherwise full volume for the listener.
 */

import { ApiError, tts, type Language } from "@/lib/api";
import { speak, stopSpeaking } from "@/lib/speech";

export interface SayOptions {
  privately?: boolean;
  /** Speak in this voice instead of the user's chosen one (voice previews in Settings). */
  voice?: string;
}

const PRIVATE_VOLUME = 0.35;
const audioCache = new Map<string, string>(); // "voice|lang|text" -> object URL
let serverHasVoice = true; // false once the server says it has no voice key (503)
let chosenVoice: string | undefined; // undefined = the server's default voice
let current: HTMLAudioElement | null = null;

/** Set the voice Echo speaks with (from the user's settings). */
export function setVoice(voice: string | undefined): void {
  chosenVoice = voice;
}

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

async function serverAudio(text: string, language: Language, voice: string | undefined): Promise<string | null> {
  const key = `${voice ?? ""}|${language}|${text}`;
  const cached = audioCache.get(key);
  if (cached) return cached;
  if (!serverHasVoice) return null;
  try {
    const url = URL.createObjectURL(await tts(text, language, voice));
    audioCache.set(key, url);
    return url;
  } catch (err) {
    if (err instanceof ApiError && err.status === 503) serverHasVoice = false; // no ElevenLabs key
    return null;
  }
}

let latest = 0; // each sayAloud/stopVoice call gets a number; only the newest one may start playing

export async function sayAloud(text: string, language: Language, opts: SayOptions = {}): Promise<void> {
  if (!text.trim()) return;
  const mine = ++latest;
  const volume = opts.privately ? PRIVATE_VOLUME : 1;
  const url = await serverAudio(text, language, opts.voice ?? chosenVoice);
  if (mine !== latest) return; // something newer was said (or stopped) while this was loading
  if (url) return playUrl(url, volume);
  await speak(text, language, { volume, rate: 0.9 }); // same pace as the natural voices
}

/** Stop whatever Echo is saying, including a sentence that is still loading. */
export function stopVoice(): void {
  latest++;
  current?.pause();
  current = null;
  stopSpeaking();
}

/** Fetch a sentence in the chosen voice ahead of time, so it plays instantly later. */
export function preloadVoice(text: string, language: Language): void {
  if (text.trim()) void serverAudio(text, language, chosenVoice);
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
