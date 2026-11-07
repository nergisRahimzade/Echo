"use client";

import { useEffect, useState } from "react";
import { Hand, Loader2, Mic, MicOff, Pointer, Square } from "lucide-react";
import { useRecorder, type Recording } from "@/lib/useRecorder";

export type RecordMode = "hold" | "tap";
const MODE_KEY = "echo.recordMode";

function loadMode(): RecordMode {
  try {
    return window.localStorage.getItem(MODE_KEY) === "tap" ? "tap" : "hold";
  } catch {
    return "hold";
  }
}

function formatTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * The big record button.
 * - "hold" mode: press and hold to record, let go to stop.
 * - "tap" mode: tap once to start, tap again to stop (for users who can't hold).
 * Keyboard / switch access: Space or Enter works the same way.
 */
export default function HoldToRecord({
  onRecorded,
  disabled = false,
  showModeToggle = true,
}: {
  onRecorded: (rec: Recording) => void;
  disabled?: boolean;
  showModeToggle?: boolean;
}) {
  const [tooShort, setTooShort] = useState(false);
  const { status, level, elapsedMs, start, stop, isRecording } = useRecorder({
    onRecorded,
    onTooShort: () => setTooShort(true),
  });
  const [mode, setMode] = useState<RecordMode>("hold");
  // The "hold longer" hint disappears after a few seconds or when a new recording starts.
  useEffect(() => {
    if (!tooShort) return;
    const t = setTimeout(() => setTooShort(false), 3000);
    return () => clearTimeout(t);
  }, [tooShort]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset hint when recording starts
    if (isRecording) setTooShort(false);
  }, [isRecording]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is only readable after mount
  useEffect(() => setMode(loadMode()), []);

  const toggleMode = () => {
    const next: RecordMode = mode === "hold" ? "tap" : "hold";
    setMode(next);
    try {
      window.localStorage.setItem(MODE_KEY, next);
    } catch {
      /* ignore */
    }
  };

  const busy = status === "starting";
  const blocked = disabled || status === "denied" || status === "unsupported";

  // --- Hold mode: pointer down/up. Pointer capture keeps recording if the finger slides off. ---
  const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (mode !== "hold" || blocked || e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    start();
  };
  const onPointerUp = () => {
    if (mode === "hold") stop();
  };

  // --- Tap mode: click toggles. ---
  const onClick = () => {
    if (mode !== "tap" || blocked) return;
    if (isRecording || busy) stop();
    else start();
  };

  // --- Keyboard / switch access ---
  const isActivationKey = (e: React.KeyboardEvent) => e.key === " " || e.key === "Enter";
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!isActivationKey(e) || e.repeat || blocked) return;
    e.preventDefault();
    if (mode === "hold") start();
    else if (isRecording || busy) stop();
    else start();
  };
  const onKeyUp = (e: React.KeyboardEvent) => {
    if (!isActivationKey(e)) return;
    e.preventDefault();
    if (mode === "hold") stop();
  };

  const label =
    status === "denied"
      ? "Microphone blocked"
      : status === "unsupported"
        ? "Recording not supported in this browser"
        : isRecording
          ? mode === "hold"
            ? "Recording, let go to stop"
            : "Recording, tap to stop"
          : mode === "hold"
            ? "Hold to talk"
            : "Tap to talk";

  const Icon = blocked && !disabled ? MicOff : busy ? Loader2 : isRecording ? (mode === "tap" ? Square : Mic) : Mic;

  return (
    <div className="flex w-full max-w-md flex-col items-center gap-4">
      <div className="relative w-full">
        {/* Level halo: grows with the loudness of the voice */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-3xl bg-primary/30 transition-transform duration-75"
          style={{ transform: `scale(${isRecording ? 1.02 + level * 0.12 : 1})` }}
        />
        <button
          type="button"
          aria-label={label}
          aria-pressed={isRecording}
          disabled={blocked}
          onPointerDown={onPointerDown}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onClick={onClick}
          onKeyDown={onKeyDown}
          onKeyUp={onKeyUp}
          onContextMenu={(e) => e.preventDefault()}
          className={`relative flex min-h-[180px] w-full flex-col items-center justify-center gap-3 rounded-3xl px-6 py-8 shadow-lg transition focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-primary disabled:opacity-50 ${
            isRecording ? "scale-[0.98] bg-danger text-white" : "bg-primary text-primary-foreground"
          } ${tooShort ? "animate-shake" : ""}`}
        >
          <Icon aria-hidden className={`h-16 w-16 ${busy ? "animate-spin" : ""}`} strokeWidth={2.5} />
          <span className="text-2xl font-semibold">{label}</span>
        </button>
      </div>

      {tooShort && (
        <p role="status" className="flex items-center gap-2 text-lg font-semibold text-danger" data-testid="too-short">
          <Hand aria-hidden className="h-7 w-7" />
          {mode === "hold" ? "Hold longer" : "Speak a little longer"}
        </p>
      )}

      {/* Timer + level bar (visible while recording) */}
      <div className={`flex w-full items-center gap-4 ${isRecording ? "" : "invisible"}`} aria-hidden={!isRecording}>
        <span className="min-w-16 font-mono text-2xl tabular-nums" role="timer" aria-live="off">
          {formatTime(elapsedMs)}
        </span>
        <div className="h-4 flex-1 overflow-hidden rounded-full bg-border">
          <div
            data-testid="level-bar"
            className="h-full rounded-full bg-danger transition-[width] duration-75"
            style={{ width: `${level * 100}%` }}
          />
        </div>
      </div>

      {showModeToggle && (
        <button
          type="button"
          onClick={toggleMode}
          disabled={isRecording}
          aria-label={mode === "hold" ? "Switch to tap to start and stop" : "Switch to press and hold"}
          title={mode === "hold" ? "Switch to tap mode" : "Switch to hold mode"}
          className="flex min-h-16 min-w-16 items-center justify-center gap-2 rounded-2xl border-2 border-border bg-surface px-4 text-lg transition active:scale-95 disabled:opacity-40"
        >
          {mode === "hold" ? <Hand aria-hidden className="h-8 w-8" /> : <Pointer aria-hidden className="h-8 w-8" />}
          <span className="text-muted">{mode === "hold" ? "Hold" : "Tap"}</span>
        </button>
      )}
    </div>
  );
}
