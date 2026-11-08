"use client";

import { useEffect } from "react";
import { ThumbsDown, ThumbsUp, Volume2 } from "lucide-react";
import type { TranslateResult } from "@/lib/api";
import { sayAloud } from "@/lib/voice";
import { useT } from "@/lib/i18n";

/**
 * Echo isn't sure: it plays its guess to the USER only (quietly) and waits.
 * Three huge icons, each thumb with a short line of text under it for those who can read.
 * `lastTry` = the user already said one guess was wrong; the next 👎 brings the helper's keyboard.
 */
export default function CheckPanel({
  result,
  busy,
  lastTry = false,
  onUp,
  onDown,
}: {
  result: TranslateResult;
  busy: boolean;
  lastTry?: boolean;
  onUp: () => void;
  onDown: () => void;
}) {
  const t = useT();
  const replay = () => void sayAloud(result.sentence, result.language, { privately: true });

  // Play the guess privately as soon as the panel appears.
  useEffect(() => {
    void sayAloud(result.sentence, result.language, { privately: true });
  }, [result.sentence, result.language]);

  return (
    <div className="flex w-full flex-col items-center gap-6" data-testid="check-panel">
      <button
        type="button"
        onClick={replay}
        disabled={busy}
        // Keyboard / switch users land on "hear it again", never straight on yes or no.
        autoFocus
        aria-label={t("talk.hearGuess")}
        className="flex h-24 w-24 items-center justify-center rounded-full border-4 border-primary text-primary transition active:scale-95 disabled:opacity-50"
      >
        <Volume2 aria-hidden className="h-12 w-12" strokeWidth={2.5} />
      </button>
      <div className="grid w-full max-w-md grid-cols-2 items-start gap-4">
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={onDown}
            disabled={busy}
            aria-label={t("talk.no")}
            aria-describedby="check-down-help"
            data-testid="check-down"
            className="flex aspect-square w-full items-center justify-center rounded-3xl bg-danger text-danger-foreground shadow-lg transition active:scale-95 disabled:opacity-50"
          >
            <ThumbsDown aria-hidden className="h-20 w-20" strokeWidth={2.5} />
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
            className="flex aspect-square w-full items-center justify-center rounded-3xl bg-success text-success-foreground shadow-lg transition active:scale-95 disabled:opacity-50"
          >
            <ThumbsUp aria-hidden className="h-20 w-20" strokeWidth={2.5} />
          </button>
          <p id="check-up-help" className="text-center leading-snug" data-testid="check-up-help">
            {t("talk.upHelp")}
          </p>
        </div>
      </div>
    </div>
  );
}
