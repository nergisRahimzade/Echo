"use client";

import { useState } from "react";
import { Keyboard, Loader2, Send, X } from "lucide-react";
import { addTurn, ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * Optional, for a helper: type what the OTHER person said, so Echo knows the topic.
 * Collapsed to a keyboard icon until opened.
 */
export default function HelperTurnInput({
  userId,
  sessionId,
  onAdded,
}: {
  userId: string;
  sessionId: string;
  onAdded?: (text: string) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      await addTurn(userId, sessionId, value);
      onAdded?.(value);
      setText("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("talk.saveError"));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("talk.otherSaid")}
        title={t("talk.otherSaid")}
        className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-border bg-surface transition active:scale-95"
      >
        <Keyboard aria-hidden className="h-8 w-8" />
      </button>
    );
  }

  return (
    <form onSubmit={send} className="flex w-full max-w-md flex-col gap-2" data-testid="helper-turn">
      <div className="flex gap-2">
        <input
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          aria-label={t("talk.otherSaidInput")}
          placeholder="…"
          className="min-h-16 min-w-0 flex-1 rounded-2xl border-2 border-border bg-surface px-4 text-xl outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          aria-label={t("talk.saveOtherSaid")}
          className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground disabled:opacity-40"
        >
          {busy ? <Loader2 aria-hidden className="h-8 w-8 animate-spin" /> : <Send aria-hidden className="h-8 w-8" />}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label={t("common.close")}
          className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border-2 border-border"
        >
          <X aria-hidden className="h-8 w-8" />
        </button>
      </div>
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
    </form>
  );
}
