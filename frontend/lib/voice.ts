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

/** Quieter than for the listener, but loud enough that the user clearly hears the guess. */
const PRIVATE_VOLUME = 0.6;
/** Speaking pace for every voice (ElevenLabs uses the same 0.85 on the server). */
export const SPEECH_RATE = 0.85;
// "voice|lang|text" -> object URL. Holds the promise, so a sentence that is still loading
// (e.g. preloaded) is not requested a second time.
const audioCache = new Map<string, Promise<string | null>>();
let serverHasVoice = true; // false once the server says it has no voice key (503)
let chosenVoice: string | undefined; // undefined = the server's default voice

/** Set the voice Echo speaks with (from the user's settings). */
export function setVoice(voice: string | undefined): void {
  chosenVoice = voice;
}

// One shared <audio> element for everything Echo says. Phones (Safari especially) only let a page
// play sound that starts from a tap; once this element has played inside a tap, it may play later
// on its own too, e.g. the guess that arrives a few seconds after the user stops recording.
let player: HTMLAudioElement | null = null;
let unlocked = false;
let finishCurrent: (() => void) | null = null; // resolves the sayAloud() that is playing now
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

function getPlayer(): HTMLAudioElement {
  player ??= new Audio();
  return player;
}

/** Call from a tap/click/key handler (the record button does) so later sounds may autoplay. */
export function unlockAudio(): void {
  if (unlocked || typeof window === "undefined") return;
  unlocked = true;
  const audio = getPlayer();
  if (!audio.paused) return; // already playing something: it is unlocked
  audio.src = SILENCE;
  audio.play().catch(() => {
    unlocked = false; // try again on the next tap
  });
}

function stopCurrent(): void {
  player?.pause();
  finishCurrent?.();
  finishCurrent = null;
}

function playUrl(url: string, volume: number): Promise<void> {
  return new Promise((resolve) => {
    stopCurrent();
    stopSpeaking();
    const audio = getPlayer();
    finishCurrent = resolve;
    audio.onended = audio.onerror = () => {
      if (finishCurrent === resolve) finishCurrent = null;
      resolve();
    };
    audio.src = url;
    audio.volume = volume;
    audio.play().catch(() => resolve());
  });
}

function serverAudio(text: string, language: Language, voice: string | undefined): Promise<string | null> {
  const key = `${voice ?? ""}|${language}|${text}`;
  const cached = audioCache.get(key);
  if (cached) return cached;
  if (!serverHasVoice) return Promise.resolve(null);
  const loading = tts(text, language, voice)
    .then((blob) => URL.createObjectURL(blob))
    .catch((err) => {
      if (err instanceof ApiError && err.status === 503) serverHasVoice = false; // no ElevenLabs key
      audioCache.delete(key); // a one-off failure: try again next time
      return null;
    });
  audioCache.set(key, loading);
  return loading;
}

let latest = 0; // each sayAloud/stopVoice call gets a number; only the newest one may start playing

export async function sayAloud(text: string, language: Language, opts: SayOptions = {}): Promise<void> {
  if (!text.trim()) return;
  const mine = ++latest;
  const volume = opts.privately ? PRIVATE_VOLUME : 1;
  const url = await serverAudio(text, language, opts.voice ?? chosenVoice);
  if (mine !== latest) return; // something newer was said (or stopped) while this was loading
  if (url) return playUrl(url, volume);
  await speak(text, language, { volume, rate: SPEECH_RATE }); // same pace as the natural voices
}

/** Stop whatever Echo is saying, including a sentence that is still loading. */
export function stopVoice(): void {
  latest++;
  stopCurrent();
  stopSpeaking();
}

/** Fetch a sentence in the chosen voice ahead of time, so it plays instantly later. */
export function preloadVoice(text: string, language: Language): void {
  if (text.trim()) void serverAudio(text, language, chosenVoice);
}

/** Like preloadVoice, but can be awaited (never throws): show a screen only once its sound is ready. */
export async function loadVoice(text: string, language: Language): Promise<void> {
  if (text.trim()) await serverAudio(text, language, chosenVoice);
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
