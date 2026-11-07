"use client";

import { useState } from "react";
import { HandHelping, Loader2, Send } from "lucide-react";
import { useT } from "@/lib/i18n";

/**
 * After two wrong guesses Echo stops guessing. A big "helper" icon opens a text box where the
 * listener or a caregiver types what was meant; it is saved as a correction Echo learns from.
 */
export default function HelperFix({ onSubmit }: { onSubmit: (text: string) => Promise<void> }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("talk.askHelper")}
        data-testid="helper-icon"
        className="flex h-36 w-36 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition active:scale-95"
      >
        <HandHelping aria-hidden className="h-20 w-20" strokeWidth={2} />
      </button>
    );
  }

  return (
    <form
      className="flex w-full max-w-md flex-col gap-3"
      data-testid="helper-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const value = text.trim();
        if (!value) return;
        setBusy(true);
        try {
          await onSubmit(value);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label className="flex flex-col gap-2">
        <span className="flex items-center gap-2 text-lg text-muted">
          <HandHelping aria-hidden className="h-6 w-6" /> {t("talk.helperQuestion")}
        </span>
        <textarea
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          maxLength={500}
          className="rounded-2xl border-2 border-border bg-surface p-4 text-2xl outline-none focus:border-primary"
        />
      </label>
      <button
        type="submit"
        disabled={busy || !text.trim()}
        aria-label={t("talk.saveAndSay")}
        className="flex min-h-20 items-center justify-center rounded-3xl bg-primary text-primary-foreground shadow-lg transition active:scale-95 disabled:opacity-40"
      >
        {busy ? <Loader2 aria-hidden className="h-9 w-9 animate-spin" /> : <Send aria-hidden className="h-9 w-9" />}
      </button>
    </form>
  );
}
