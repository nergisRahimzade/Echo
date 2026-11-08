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
import { enroll, getPhrases, getSamples, type Language, type Phrase } from "@/lib/api";
import { preloadVoice, sayAloud, stopVoice } from "@/lib/voice";
import type { Recording } from "@/lib/useRecorder";
import { showError, toUiError, useI18n, type UiError } from "@/lib/i18n";

type Stage = "loading" | "start" | "phrase" | "finished" | "error";

/**
 * Enrollment: Echo says each everyday phrase aloud, the user repeats it, and the
 * recording is saved with the phrase. No reading needed: pictures, sounds and icons only.
 */
export default function EnrollFlow() {
  const user = useUser();
  const { t } = useI18n();
  const [lang, setLang] = useState<Language>(user.main_language === "en" ? "en" : "tr");
  const [stage, setStage] = useState<Stage>("loading");
  const [phrases, setPhrases] = useState<Phrase[]>([]);
  const [recorded, setRecorded] = useState<Set<string>>(new Set());
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [index, setIndex] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<UiError | null>(null);

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
        setError(toUiError(err, "enroll.loadError"));
        setStage("error");
      });
    return () => {
      cancelled = true;
      stopVoice();
    };
  }, [lang, user.user_id]);

  const phrase = phrases[index];

  // Echo says the phrase aloud (in the voice chosen in Settings) each time a new one appears,
  // and loads the next phrase's audio in the background so it plays without a wait.
  useEffect(() => {
    if (stage !== "phrase" || !phrase) return;
    void sayAloud(phrase.text, lang);
    const next = phrases[(index + 1) % phrases.length];
    if (next && next.id !== phrase.id) preloadVoice(next.text, lang);
  }, [stage, phrase, lang, phrases, index]);

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
      stopVoice();
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
      setError(toUiError(err, "enroll.saveError"));
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
      <div className="flex gap-2" data-guide="enroll-language">
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
    return <Loader2 aria-label={t("common.loading")} className="mx-auto mt-24 h-12 w-12 animate-spin text-muted" />;
  }

  if (stage === "error") {
    return (
      <div className="mt-16 flex flex-col items-center gap-6 px-4 text-center" role="alert">
        <AlertTriangle aria-hidden className="h-20 w-20 text-danger" />
        <p className="text-lg text-muted">{error && showError(error, t)}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          aria-label={t("common.tryAgain")}
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
        <h1 className="sr-only">{t("enroll.heading")}</h1>
        {languageSwitch}
        <CheckCircle2 aria-hidden className="h-32 w-32 text-success" strokeWidth={2} />
        <div className="shrink-0" data-guide="enroll-progress">
          <ProgressRing done={doneCount} total={total} size={96} label={t("enroll.progress", { done: doneCount, total })} />
        </div>
        <div className="flex flex-wrap justify-center gap-4" data-guide="enroll-finished-actions">
          <IconLink href="/words" label={t("enroll.addWords")} icon={<UsersRound className="h-10 w-10" />} primary />
          <IconLink href="/" label={t("common.home")} icon={<House className="h-10 w-10" />} />
          <IconButton onClick={recordAgain} label={t("enroll.recordAllAgain")} icon={<RotateCcw className="h-10 w-10" />} />
        </div>
      </div>
    );
  }

  if (stage === "start") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10">
        <h1 className="sr-only">{t("enroll.heading")}</h1>
        {languageSwitch}
        <div className="shrink-0" data-guide="enroll-progress">
          <ProgressRing done={doneCount} total={total} size={96} label={t("enroll.progress", { done: doneCount, total })} />
        </div>
        <div className="flex items-center gap-3 text-muted" aria-hidden>
          <Volume2 className="h-10 w-10" />
          <ArrowRight className="h-6 w-6" />
          <span className="text-4xl">🗣️</span>
        </div>
        <button
          type="button"
          onClick={() => setStage("phrase")}
          data-guide="enroll-start"
          aria-label={t("enroll.start")}
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
      <h1 className="sr-only">{t("enroll.heading")}</h1>
      <div className="flex w-full items-center justify-between gap-4">
        <div className="shrink-0" data-guide="enroll-progress">
          <ProgressRing done={doneCount} total={total} label={t("enroll.progress", { done: doneCount, total })} />
        </div>
        {languageSwitch}
        <div className="shrink-0" data-guide="enroll-skip">
          <IconButton
            onClick={skip}
            disabled={uploading}
            label={t("enroll.skip")}
            icon={<SkipForward className="h-8 w-8" />}
            small
          />
        </div>
      </div>

      {/* The phrase: a big picture, heard aloud. The text is small, for helpers. */}
      <div className="flex w-full items-center justify-center gap-6" data-testid="enroll-phrase" data-phrase-id={phrase.id} data-guide="enroll-phrase">
        <span aria-hidden className="text-[110px] leading-none">
          {phrase.icon}
        </span>
        <button
          type="button"
          onClick={() => void sayAloud(phrase.text, lang)}
          aria-label={t("enroll.hearAgain")}
          className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-primary text-primary transition active:scale-95"
        >
          <Volume2 aria-hidden className="h-10 w-10" strokeWidth={2.5} />
        </button>
      </div>
      <p className="text-center text-[22px] leading-[1.4] text-muted">{phrase.text}</p>

      {recording ? (
        <div className="flex w-full items-center justify-center gap-5" data-testid="enroll-review">
          <IconButton
            onClick={() => setRecording(null)}
            disabled={uploading}
            label={t("enroll.recordAgain")}
            icon={<RotateCcw className="h-10 w-10" />}
          />
          <AudioPlayButton blob={recording.blob} label={t("enroll.listen")} />
          <button
            type="button"
            onClick={saveAndNext}
            disabled={uploading}
            aria-label={t("enroll.saveNext")}
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
          <AlertTriangle aria-hidden className="h-6 w-6" /> {showError(error, t)}
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
