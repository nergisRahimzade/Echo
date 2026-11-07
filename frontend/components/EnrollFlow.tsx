"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  House,
  Loader2,
  Play,
  RotateCcw,
  SkipForward,
  UsersRound,
  Volume2,
} from "lucide-react";
import AudioPlayButton from "@/components/AudioPlayButton";
import Flag from "@/components/Flag";
import HoldToRecord from "@/components/HoldToRecord";
import ProgressRing from "@/components/ProgressRing";
import { useUser } from "@/components/UserGate";
import { ApiError, enroll, getPhrases, getSamples, type Language, type Phrase } from "@/lib/api";
import { speak, stopSpeaking } from "@/lib/speech";
import type { Recording } from "@/lib/useRecorder";

type Stage = "loading" | "start" | "phrase" | "finished" | "error";

/**
 * Enrollment: Echo says each everyday phrase aloud, the user repeats it, and the
 * recording is saved with the phrase. No reading needed: pictures, sounds and icons only.
 */
export default function EnrollFlow() {
  const user = useUser();
  const [lang, setLang] = useState<Language>(user.main_language === "en" ? "en" : "tr");
  const [stage, setStage] = useState<Stage>("loading");
  const [phrases, setPhrases] = useState<Phrase[]>([]);
  const [recorded, setRecorded] = useState<Set<string>>(new Set());
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [index, setIndex] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the phrases and what this user already recorded (so enrollment can resume).
  useEffect(() => {
    let cancelled = false;
    Promise.all([getPhrases(lang), getSamples(user.user_id)])
      .then(([list, samples]) => {
        if (cancelled) return;
        const done = new Set(
          samples.filter((s) => s.language === lang && s.phrase_id).map((s) => s.phrase_id as string),
        );
        setPhrases(list);
        setRecorded(done);
        setSkipped(new Set());
        setRecording(null);
        const first = list.findIndex((p) => !done.has(p.id));
        setIndex(first === -1 ? 0 : first);
        setStage(first === -1 ? "finished" : "start");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load the phrases.");
        setStage("error");
      });
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, [lang, user.user_id]);

  const phrase = phrases[index];

  // Echo says the phrase aloud each time a new one appears.
  useEffect(() => {
    if (stage === "phrase" && phrase) void speak(phrase.text, lang);
  }, [stage, phrase, lang]);

  const goToNext = useCallback(
    (doneNow: Set<string>, skippedNow: Set<string>) => {
      setRecording(null);
      for (let step = 1; step <= phrases.length; step++) {
        const i = (index + step) % phrases.length;
        const id = phrases[i].id;
        if (!doneNow.has(id) && !skippedNow.has(id)) {
          setIndex(i);
          return;
        }
      }
      stopSpeaking();
      setStage("finished");
    },
    [index, phrases],
  );

  async function saveAndNext() {
    if (!recording || !phrase) return;
    setUploading(true);
    setError(null);
    try {
      await enroll({
        userId: user.user_id,
        phraseText: phrase.text,
        phraseId: phrase.id,
        language: lang,
        audio: recording.blob,
      });
      const doneNow = new Set(recorded).add(phrase.id);
      setRecorded(doneNow);
      goToNext(doneNow, skipped);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saving failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  function skip() {
    if (!phrase) return;
    const skippedNow = new Set(skipped).add(phrase.id);
    setSkipped(skippedNow);
    goToNext(recorded, skippedNow);
  }

  function recordAgain() {
    // Extra recordings of the same phrases help Echo, so allow a second round.
    setRecorded(new Set());
    setSkipped(new Set());
    setIndex(0);
    setStage("phrase");
  }

  const total = phrases.length;
  const doneCount = useMemo(() => phrases.filter((p) => recorded.has(p.id)).length, [phrases, recorded]);

  const languageSwitch =
    user.main_language === "both" ? (
      <div className="flex gap-2">
        {(["tr", "en"] as const).map((l) => (
          <button
            key={l}
            type="button"
            aria-pressed={lang === l}
            aria-label={l === "tr" ? "Türkçe" : "English"}
            onClick={() => setLang(l)}
            className={`flex min-h-16 min-w-16 items-center justify-center rounded-2xl border-4 p-2 ${
              lang === l ? "border-primary" : "border-transparent opacity-60"
            }`}
          >
            <Flag code={l === "tr" ? "tr" : "gb"} className="h-8 w-12" />
          </button>
        ))}
      </div>
    ) : null;

  if (stage === "loading") {
    return <Loader2 aria-label="Loading" className="mx-auto mt-24 h-12 w-12 animate-spin text-muted" />;
  }

  if (stage === "error") {
    return (
      <div className="mt-16 flex flex-col items-center gap-6 px-4 text-center" role="alert">
        <AlertTriangle aria-hidden className="h-20 w-20 text-danger" />
        <p className="text-lg text-muted">{error}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          aria-label="Try again"
          className="flex h-20 w-20 items-center justify-center rounded-full bg-primary text-primary-foreground"
        >
          <RotateCcw aria-hidden className="h-10 w-10" />
        </button>
      </div>
    );
  }

  if (stage === "finished") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10" data-testid="enroll-finished">
        {languageSwitch}
        <CheckCircle2 aria-hidden className="h-32 w-32 text-success" strokeWidth={2} />
        <ProgressRing done={doneCount} total={total} size={96} label={`${doneCount} of ${total} phrases recorded`} />
        <div className="flex flex-wrap justify-center gap-4">
          <IconLink href="/words" label="Add names and places" icon={<UsersRound className="h-10 w-10" />} primary />
          <IconLink href="/" label="Home" icon={<House className="h-10 w-10" />} />
          <IconButton onClick={recordAgain} label="Record the phrases again" icon={<RotateCcw className="h-10 w-10" />} />
        </div>
      </div>
    );
  }

  if (stage === "start") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10">
        {languageSwitch}
        <ProgressRing done={doneCount} total={total} size={96} label={`${doneCount} of ${total} phrases recorded`} />
        <div className="flex items-center gap-3 text-muted" aria-hidden>
          <Volume2 className="h-10 w-10" />
          <ArrowRight className="h-6 w-6" />
          <span className="text-4xl">🗣️</span>
        </div>
        <button
          type="button"
          onClick={() => setStage("phrase")}
          aria-label="Start"
          className="flex h-36 w-36 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition active:scale-95"
        >
          <Play aria-hidden className="ml-2 h-20 w-20" />
        </button>
      </div>
    );
  }

  // stage === "phrase"
  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center gap-6 px-4 py-6">
      <div className="flex w-full items-center justify-between gap-4">
        <ProgressRing done={doneCount} total={total} label={`${doneCount} of ${total} phrases recorded`} />
        {languageSwitch}
        <IconButton
          onClick={skip}
          disabled={uploading}
          label="Skip this phrase"
          icon={<SkipForward className="h-8 w-8" />}
          small
        />
      </div>

      {/* The phrase: a big picture, heard aloud. The text is small, for helpers. */}
      <div className="flex w-full items-center justify-center gap-6" data-testid="enroll-phrase" data-phrase-id={phrase.id}>
        <span aria-hidden className="text-[110px] leading-none">
          {phrase.icon}
        </span>
        <button
          type="button"
          onClick={() => speak(phrase.text, lang)}
          aria-label="Hear the phrase again"
          className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-primary text-primary transition active:scale-95"
        >
          <Volume2 aria-hidden className="h-10 w-10" strokeWidth={2.5} />
        </button>
      </div>
      <p className="text-center text-xl text-muted">{phrase.text}</p>

      {recording ? (
        <div className="flex w-full items-center justify-center gap-5" data-testid="enroll-review">
          <IconButton
            onClick={() => setRecording(null)}
            disabled={uploading}
            label="Record again"
            icon={<RotateCcw className="h-10 w-10" />}
          />
          <AudioPlayButton blob={recording.blob} label="Listen to your recording" />
          <button
            type="button"
            onClick={saveAndNext}
            disabled={uploading}
            aria-label="Save and go to the next phrase"
            className="flex h-24 w-24 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition active:scale-95 disabled:opacity-60"
          >
            {uploading ? <Loader2 aria-hidden className="h-12 w-12 animate-spin" /> : <Check aria-hidden className="h-12 w-12" strokeWidth={3} />}
          </button>
        </div>
      ) : (
        <HoldToRecord onRecorded={setRecording} />
      )}

      {error && (
        <p role="alert" className="flex items-center gap-2 text-lg text-danger">
          <AlertTriangle aria-hidden className="h-6 w-6" /> {error}
        </p>
      )}
    </div>
  );
}

function IconButton({
  onClick,
  label,
  icon,
  disabled,
  small,
}: {
  onClick: () => void;
  label: string;
  icon: React.ReactNode;
  disabled?: boolean;
  small?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`flex ${small ? "h-16 w-16" : "h-20 w-20"} items-center justify-center rounded-full border-2 border-border bg-surface text-foreground transition active:scale-95 disabled:opacity-40`}
    >
      {icon}
    </button>
  );
}

function IconLink({ href, label, icon, primary }: { href: string; label: string; icon: React.ReactNode; primary?: boolean }) {
  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      className={`flex h-24 w-24 items-center justify-center rounded-full shadow-md transition active:scale-95 ${
        primary ? "bg-primary text-primary-foreground" : "border-2 border-border bg-surface"
      }`}
    >
      {icon}
    </Link>
  );
}
