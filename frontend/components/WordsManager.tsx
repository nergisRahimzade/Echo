"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, MapPin, Mic, PawPrint, Plus, Star, UserRound, X } from "lucide-react";
import HoldToRecord from "@/components/HoldToRecord";
import { useUser } from "@/components/UserGate";
import { addWords, ApiError, deleteWord, enroll, getSamples, getWords, type PersonalWord, type WordKind } from "@/lib/api";
import { speakingLanguage } from "@/lib/user";
import type { Recording } from "@/lib/useRecorder";

const KINDS: { kind: WordKind; label: string; Icon: typeof UserRound }[] = [
  { kind: "person", label: "Person", Icon: UserRound },
  { kind: "place", label: "Place", Icon: MapPin },
  { kind: "pet", label: "Pet", Icon: PawPrint },
  { kind: "other", label: "Other", Icon: Star },
];
const kindIcon = (kind: WordKind) => KINDS.find((k) => k.kind === kind)!.Icon;
const sameWord = (a: string, b: string) => a.toLocaleLowerCase() === b.toLocaleLowerCase();

/**
 * Names of family, friends, places and pets. A helper usually types them;
 * the user can record how they say each one (saved as an enrollment sample).
 */
export default function WordsManager() {
  const user = useUser();
  const language = speakingLanguage(user);
  const [words, setWords] = useState<PersonalWord[]>([]);
  const [recorded, setRecorded] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const [kind, setKind] = useState<WordKind>("person");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [recordingFor, setRecordingFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getWords(user.user_id), getSamples(user.user_id)])
      .then(([list, samples]) => {
        setWords(list);
        // A name counts as recorded if there is a sample with no phrase id and the same text.
        setRecorded(new Set(samples.filter((s) => !s.phrase_id).map((s) => s.text.toLocaleLowerCase())));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load the words."))
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
      setError(err instanceof ApiError ? err.message : "Could not save the word.");
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
      setError(err instanceof ApiError ? err.message : "Could not delete the word.");
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
      setError(err instanceof ApiError ? err.message : "Could not save the recording.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loader2 aria-label="Loading" className="mx-auto mt-24 h-12 w-12 animate-spin text-muted" />;

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-6">
      <div>
        <h1 className="text-3xl font-bold">Names and places</h1>
        <p className="mt-1 text-lg text-muted">Family, friends, places and pets. A helper can type them.</p>
      </div>

      <form onSubmit={add} className="flex flex-col gap-4 rounded-2xl border-2 border-border bg-surface p-4">
        <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Type">
          {KINDS.map(({ kind: k, label, Icon }) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              aria-label={label}
              title={label}
              onClick={() => setKind(k)}
              className={`flex min-h-16 flex-col items-center justify-center gap-1 rounded-2xl border-4 transition active:scale-95 ${
                kind === k ? "border-primary bg-primary/10" : "border-border"
              }`}
            >
              <Icon aria-hidden className="h-8 w-8" />
              <span className="text-sm">{label}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={60}
            aria-label="Name or place"
            placeholder="Zeynep, Kadıköy…"
            className="min-h-16 min-w-0 flex-1 rounded-2xl border-2 border-border bg-background px-4 text-2xl outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            aria-label="Add"
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground transition active:scale-95 disabled:opacity-40"
          >
            <Plus aria-hidden className="h-9 w-9" strokeWidth={3} />
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="text-lg text-danger">
          {error}
        </p>
      )}

      <ul className="flex flex-col gap-3" aria-label="Saved names and places" data-testid="word-list">
        {words.map((w) => {
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
                  aria-label={isRecorded ? `Record ${w.word} again` : `Record how you say ${w.word}`}
                  className={`relative flex h-16 w-16 items-center justify-center rounded-full border-2 transition active:scale-95 ${
                    open ? "border-primary bg-primary text-primary-foreground" : "border-border"
                  }`}
                >
                  <Mic aria-hidden className="h-8 w-8" />
                  {isRecorded && (
                    <span className="absolute -right-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full bg-success text-white" data-testid="recorded-badge">
                      <Check aria-hidden className="h-5 w-5" strokeWidth={3} />
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => remove(w.word)}
                  aria-label={`Delete ${w.word}`}
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
  );
}
