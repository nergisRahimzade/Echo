"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Loader2, MapPin, Mic, PawPrint, Plus, Star, UserRound, X } from "lucide-react";
import HoldToRecord from "@/components/HoldToRecord";
import { useUser } from "@/components/UserGate";
import { addWords, deleteWord, enroll, getSamples, getWords, type PersonalWord, type WordKind } from "@/lib/api";
import { speakingLanguage } from "@/lib/user";
import type { Recording } from "@/lib/useRecorder";
import { showError, toUiError, useT, type UiError } from "@/lib/i18n";

const KINDS: { kind: WordKind; Icon: typeof UserRound }[] = [
  { kind: "person", Icon: UserRound },
  { kind: "place", Icon: MapPin },
  { kind: "pet", Icon: PawPrint },
  { kind: "other", Icon: Star },
];
const kindIcon = (kind: WordKind) => KINDS.find((k) => k.kind === kind)!.Icon;
const sameWord = (a: string, b: string) => a.toLocaleLowerCase() === b.toLocaleLowerCase();

/**
 * Names of family, friends, places and pets. A helper usually types them;
 * the user can record how they say each one (saved as an enrollment sample).
 * One tab per kind: a word added in a tab is saved as that kind and listed only in that tab.
 */
export default function WordsManager() {
  const user = useUser();
  const t = useT();
  const language = speakingLanguage(user);
  const [words, setWords] = useState<PersonalWord[]>([]);
  const [recorded, setRecorded] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const [kind, setKind] = useState<WordKind>("person"); // the open tab
  const tabRefs = useRef<Partial<Record<WordKind, HTMLButtonElement | null>>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [recordingFor, setRecordingFor] = useState<string | null>(null);
  const [error, setError] = useState<UiError | null>(null);

  useEffect(() => {
    Promise.all([getWords(user.user_id), getSamples(user.user_id)])
      .then(([list, samples]) => {
        setWords(list);
        // A name counts as recorded if there is a sample with no phrase id and the same text.
        setRecorded(new Set(samples.filter((s) => !s.phrase_id).map((s) => s.text.toLocaleLowerCase())));
      })
      .catch((err) => setError(toUiError(err, "words.loadError")))
      .finally(() => setLoading(false));
  }, [user.user_id]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    const word = text.trim().replace(/\s+/g, " ");
    if (!word) return;
    setBusy(true);
    setError(null);
    try {
      await addWords(user.user_id, [{ word, kind }]);
      setWords((prev) => [...prev.filter((w) => !sameWord(w.word, word)), { word, kind }]);
      setText("");
    } catch (err) {
      setError(toUiError(err, "words.saveError"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(word: string) {
    setError(null);
    try {
      await deleteWord(user.user_id, word);
      setWords((prev) => prev.filter((w) => !sameWord(w.word, word)));
    } catch (err) {
      setError(toUiError(err, "words.deleteError"));
    }
  }

  async function saveRecording(word: string, rec: Recording) {
    setBusy(true);
    setError(null);
    try {
      await enroll({ userId: user.user_id, phraseText: word, language, audio: rec.blob });
      setRecorded((prev) => new Set(prev).add(word.toLocaleLowerCase()));
      setRecordingFor(null);
    } catch (err) {
      setError(toUiError(err, "words.recordError"));
    } finally {
      setBusy(false);
    }
  }

  const shown = words.filter((w) => w.kind === kind);
  const countOf = (k: WordKind) => words.filter((w) => w.kind === k).length;

  function openTab(k: WordKind) {
    setKind(k);
    setRecordingFor(null);
  }

  // Tabs keyboard pattern: arrow keys move between tabs, Home/End jump to the first/last.
  function onTabKey(e: React.KeyboardEvent, i: number) {
    const last = KINDS.length - 1;
    const next =
      e.key === "ArrowRight" ? (i === last ? 0 : i + 1)
      : e.key === "ArrowLeft" ? (i === 0 ? last : i - 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? last
      : null;
    if (next === null) return;
    e.preventDefault();
    const k = KINDS[next].kind;
    openTab(k);
    tabRefs.current[k]?.focus();
  }

  if (loading) return <Loader2 aria-label={t("common.loading")} className="mx-auto mt-24 h-12 w-12 animate-spin text-muted" />;

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-6">
      <div>
        <h1 className="text-3xl font-bold">{t("words.title")}</h1>
        <p className="mt-1 text-lg text-muted">{t("words.subtitle")}</p>
      </div>

      <div className="grid grid-cols-4 gap-2" role="tablist" aria-label={t("words.tabs")}>
        {KINDS.map(({ kind: k, Icon }, i) => {
          const on = kind === k;
          return (
            <button
              key={k}
              ref={(el) => {
                tabRefs.current[k] = el;
              }}
              type="button"
              role="tab"
              id={`words-tab-${k}`}
              aria-selected={on}
              aria-controls="words-panel"
              tabIndex={on ? 0 : -1}
              onClick={() => openTab(k)}
              onKeyDown={(e) => onTabKey(e, i)}
              data-testid={`words-tab-${k}`}
              className={`flex min-h-20 flex-col items-center justify-center gap-1 rounded-2xl border-4 transition active:scale-95 ${
                on ? "border-primary bg-primary text-primary-foreground shadow-md" : "border-border bg-surface"
              }`}
            >
              <Icon aria-hidden className="h-8 w-8" />
              <span className="text-sm">
                {t(`words.${k}`)} ({countOf(k)})
              </span>
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id="words-panel" aria-labelledby={`words-tab-${kind}`} className="flex flex-col gap-6">
        <form onSubmit={add} className="flex gap-3 rounded-2xl border-2 border-border bg-surface p-4">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={60}
            aria-label={t(`words.inputs.${kind}`)}
            placeholder={t(`words.placeholders.${kind}`)}
            className="min-h-16 min-w-0 flex-1 rounded-2xl border-2 border-border bg-background px-4 text-2xl outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            aria-label={t("words.add")}
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground transition active:scale-95 disabled:opacity-40"
          >
            <Plus aria-hidden className="h-9 w-9" strokeWidth={3} />
          </button>
        </form>

        {error && (
          <p role="alert" className="text-lg text-danger">
            {showError(error, t)}
          </p>
        )}

        {shown.length === 0 && (
          <p className="text-center text-lg text-muted" data-testid="words-empty">
            {t("words.empty")}
          </p>
        )}

        <ul className="flex flex-col gap-3" aria-label={t("words.list")} data-testid="word-list">
          {shown.map((w) => {
            const Icon = kindIcon(w.kind);
            const isRecorded = recorded.has(w.word.toLocaleLowerCase());
            const open = recordingFor !== null && sameWord(recordingFor, w.word);
            return (
              <li key={w.word} className="flex flex-col gap-3 rounded-2xl border-2 border-border bg-surface p-3" data-testid="word-chip">
                <div className="flex items-center gap-3">
                  <Icon aria-hidden className="h-8 w-8 shrink-0 text-primary" />
                  <span className="flex-1 truncate text-2xl font-semibold">{w.word}</span>
                  <button
                    type="button"
                    onClick={() => setRecordingFor(open ? null : w.word)}
                    aria-label={isRecorded ? t("words.recordAgain", { word: w.word }) : t("words.record", { word: w.word })}
                    className={`relative flex h-16 w-16 items-center justify-center rounded-full border-2 transition active:scale-95 ${
                      open ? "border-primary bg-primary text-primary-foreground" : "border-border"
                    }`}
                  >
                    <Mic aria-hidden className="h-8 w-8" />
                    {isRecorded && (
                      <span className="absolute -right-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full bg-success text-success-foreground" data-testid="recorded-badge">
                        <Check aria-hidden className="h-5 w-5" strokeWidth={3} />
                      </span>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(w.word)}
                    aria-label={t("words.delete", { word: w.word })}
                    className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-border text-danger transition active:scale-95"
                  >
                    <X aria-hidden className="h-8 w-8" />
                  </button>
                </div>
                {open && <HoldToRecord onRecorded={(rec) => saveRecording(w.word, rec)} disabled={busy} showModeToggle={false} />}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
