"use client";

import { useEffect, useState } from "react";
import { Hand, Loader2, Mic, MicOff, Square } from "lucide-react";
import { useRecorder, type Recording } from "@/lib/useRecorder";
import { useT } from "@/lib/i18n";
import { unlockAudio } from "@/lib/voice";

function formatTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * The big record button: tap once to start, tap again to stop.
 * Keyboard / switch access: Space or Enter works the same way.
 */
export default function HoldToRecord({
  onRecorded,
  disabled = false,
}: {
  onRecorded: (rec: Recording) => void;
  disabled?: boolean;
}) {
  const t = useT();
  const [tooShort, setTooShort] = useState(false);
  const { status, level, elapsedMs, start, stop, isRecording } = useRecorder({
    onRecorded,
    onTooShort: () => setTooShort(true),
  });
  // The "speak longer" hint disappears after a few seconds or when a new recording starts.
  useEffect(() => {
    if (!tooShort) return;
    const t = setTimeout(() => setTooShort(false), 3000);
    return () => clearTimeout(t);
  }, [tooShort]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset hint when recording starts
    if (isRecording) setTooShort(false);
  }, [isRecording]);

  const busy = status === "starting";
  const blocked = disabled || status === "denied" || status === "unsupported";

  const toggle = () => {
    unlockAudio(); // lets Echo's answer play by itself later (phones block sound not started by a tap)
    if (blocked) return;
    if (isRecording || busy) stop();
    else start();
  };

  // Space and Enter already click a button; handled here so a held key doesn't start and stop over and over.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== " " && e.key !== "Enter") return;
    e.preventDefault();
    if (!e.repeat) toggle();
  };
  // Space clicks on key-up in some browsers: cancel it so one press is one toggle.
  const onKeyUp = (e: React.KeyboardEvent) => {
    if (e.key === " " || e.key === "Enter") e.preventDefault();
  };

  const label =
    status === "denied"
      ? t("recorder.micBlocked")
      : status === "unsupported"
        ? t("recorder.unsupported")
        : isRecording
          ? t("recorder.recordingTap")
          : t("recorder.tapToTalk");

  const Icon = blocked && !disabled ? MicOff : busy ? Loader2 : isRecording ? Square : Mic;

  return (
    <div className="flex w-full max-w-md flex-col items-center gap-4">
      <div className="relative w-full" data-guide="record">
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
          data-testid="record-button"
          data-recording={isRecording}
          disabled={blocked}
          onClick={toggle}
          onKeyDown={onKeyDown}
          onKeyUp={onKeyUp}
          onContextMenu={(e) => e.preventDefault()}
          className={`relative flex min-h-[180px] w-full flex-col items-center justify-center gap-3 rounded-3xl px-6 py-8 shadow-lg transition focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-primary disabled:opacity-50 ${
            isRecording ? "scale-[0.98] bg-danger text-danger-foreground" : "bg-primary text-primary-foreground"
          } ${tooShort ? "animate-shake" : ""}`}
        >
          <Icon aria-hidden className={`h-16 w-16 ${busy ? "animate-spin" : ""}`} strokeWidth={2.5} />
          <span className="text-2xl font-semibold">{label}</span>
        </button>
      </div>

      {tooShort && (
        <p role="status" className="flex items-center gap-2 text-lg font-semibold text-danger" data-testid="too-short">
          <Hand aria-hidden className="h-7 w-7" />
          {t("recorder.speakLonger")}
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
    </div>
  );
}
