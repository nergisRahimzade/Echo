"use client";

import { useEffect } from "react";
import { Pencil, ThumbsDown, ThumbsUp, Volume2 } from "lucide-react";
import type { TranslateResult } from "@/lib/api";
import { sayAloud } from "@/lib/voice";
import { useT } from "@/lib/i18n";

/**
 * Echo isn't sure: it plays its guess to the USER only (quietly), shows the sentence, and waits.
 * Sound + sentence + buttons: 👎 / 👍 with a short line of text under each, and a pencil to
 * write the right sentence straight away (no need to press 👎 twice).
 * `lastTry` = the user already said one guess was wrong; the next 👎 brings the helper's keyboard.
 */
export default function CheckPanel({
  result,
  busy,
  lastTry = false,
  onUp,
  onDown,
  onWrite,
}: {
  result: TranslateResult;
  busy: boolean;
  lastTry?: boolean;
  onUp: () => void;
  onDown: () => void;
  onWrite: () => void;
}) {
  const t = useT();
  const replay = () => void sayAloud(result.sentence, result.language, { privately: true });

  // Play the guess privately as soon as the panel appears.
  useEffect(() => {
    void sayAloud(result.sentence, result.language, { privately: true });
  }, [result.sentence, result.language]);

  return (
    <div className="flex w-full flex-col items-center gap-5" data-testid="check-panel">
      <div className="flex w-full max-w-md items-center gap-4">
        <button
          type="button"
          onClick={replay}
          disabled={busy}
          // Keyboard / switch users land on "hear it again", never straight on yes or no.
          autoFocus
          aria-label={t("talk.hearGuess")}
          className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-primary text-primary transition active:scale-95 disabled:opacity-50"
        >
          <Volume2 aria-hidden className="h-10 w-10" strokeWidth={2.5} />
        </button>
        {/* Echo's guess, for the user to check (not yet said to the listener). */}
        <p className="flex-1 text-2xl font-semibold leading-snug sm:text-3xl" lang={result.language} data-testid="check-sentence">
          {result.sentence}
        </p>
      </div>

      <div className="grid w-full max-w-md grid-cols-2 items-start gap-4">
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={onDown}
            disabled={busy}
            aria-label={t("talk.no")}
            aria-describedby="check-down-help"
            data-testid="check-down"
            className="flex h-32 w-full items-center justify-center rounded-3xl bg-danger text-danger-foreground shadow-lg transition active:scale-95 disabled:opacity-50"
          >
            <ThumbsDown aria-hidden className="h-16 w-16" strokeWidth={2.5} />
          </button>
          <p id="check-down-help" className="text-center leading-snug" data-testid="check-down-help">
            {t(lastTry ? "talk.downHelpLast" : "talk.downHelp")}
          </p>
        </div>
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={onUp}
            disabled={busy}
            aria-label={t("talk.yes")}
            aria-describedby="check-up-help"
            data-testid="check-up"
            className="flex h-32 w-full items-center justify-center rounded-3xl bg-success text-success-foreground shadow-lg transition active:scale-95 disabled:opacity-50"
          >
            <ThumbsUp aria-hidden className="h-16 w-16" strokeWidth={2.5} />
          </button>
          <p id="check-up-help" className="text-center leading-snug" data-testid="check-up-help">
            {t("talk.upHelp")}
          </p>
        </div>
      </div>

      <WriteButton onClick={onWrite} disabled={busy} />
    </div>
  );
}

/** "Write what you meant": opens the text box at once to type the right sentence. */
export function WriteButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid="write-correction"
      className="flex min-h-16 w-full max-w-md items-center justify-center gap-3 rounded-2xl border-2 border-border bg-surface px-4 text-lg font-semibold transition active:scale-95 disabled:opacity-50"
    >
      <Pencil aria-hidden className="h-7 w-7 shrink-0" />
      {t("talk.writeIt")}
    </button>
  );
}
