"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderStatus = "idle" | "starting" | "recording" | "denied" | "unsupported";

export interface Recording {
  blob: Blob;
  durationMs: number;
  mimeType: string;
}

/** Recordings shorter than this are treated as accidental taps and dropped. */
const MIN_DURATION_MS = 300;

/** Best format the browser can record: webm/opus (Chrome, Firefox, Android), mp4 (Safari/iOS). */
function pickMimeType(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return candidates.find((t) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) ?? "";
}

/**
 * Microphone recording with a live level (0-1) and elapsed time.
 * The mic stream is opened on first use and kept open, so later recordings start instantly.
 */
export function useRecorder({
  onRecorded,
  maxDurationMs = 60_000,
}: {
  onRecorded: (rec: Recording) => void;
  maxDurationMs?: number;
}) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [level, setLevel] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const stopRequestedRef = useRef(false); // released the button before the mic was ready
  const onRecordedRef = useRef(onRecorded);
  useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const stopMeter = () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    setLevel(0);
  };

  const ensureStream = useCallback(async (): Promise<MediaStream> => {
    if (streamRef.current?.active) return streamRef.current;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    streamRef.current = stream;
    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    audioCtxRef.current = ctx;
    analyserRef.current = analyser;
    return stream;
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state === "recording") recorder.stop();
    else stopRequestedRef.current = true;
  }, []);

  const start = useCallback(async () => {
    if (recorderRef.current?.state === "recording") return;
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("unsupported");
      return;
    }
    stopRequestedRef.current = false;
    setStatus("starting");
    let stream: MediaStream;
    try {
      stream = await ensureStream();
    } catch {
      setStatus("denied");
      return;
    }
    if (stopRequestedRef.current) {
      // The user let go while we were waiting for microphone permission.
      setStatus("idle");
      return;
    }
    await audioCtxRef.current?.resume();

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recorderRef.current = recorder;
    chunksRef.current = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      stopMeter();
      setStatus("idle");
      const durationMs = performance.now() - startedAtRef.current;
      const type = recorder.mimeType || mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type });
      if (durationMs >= MIN_DURATION_MS && blob.size > 0) {
        onRecordedRef.current({ blob, durationMs, mimeType: type });
      }
    };

    startedAtRef.current = performance.now();
    recorder.start(250);
    setElapsedMs(0);
    setStatus("recording");

    // Level meter + timer, updated every animation frame.
    const analyser = analyserRef.current;
    const samples = new Float32Array(analyser?.fftSize ?? 1024);
    const tick = () => {
      const elapsed = performance.now() - startedAtRef.current;
      setElapsedMs(elapsed);
      if (analyser) {
        analyser.getFloatTimeDomainData(samples);
        let sum = 0;
        for (const s of samples) sum += s * s;
        const rms = Math.sqrt(sum / samples.length);
        setLevel(Math.min(1, rms * 6)); // speech RMS is small; scale into 0-1
      }
      if (elapsed >= maxDurationMs) {
        recorder.stop();
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [ensureStream, maxDurationMs]);

  // Release the microphone when the component goes away.
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      const recorder = recorderRef.current;
      if (recorder && recorder.state === "recording") {
        recorder.onstop = null;
        recorder.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close();
    };
  }, []);

  return { status, level, elapsedMs, start, stop, isRecording: status === "recording" };
}
