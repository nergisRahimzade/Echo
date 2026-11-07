"use client";

import { useEffect } from "react";
import { ThumbsDown, ThumbsUp, Volume2 } from "lucide-react";
import type { TranslateResult } from "@/lib/api";
import { sayAloud } from "@/lib/voice";

/**
 * Echo isn't sure: it plays its guess to the USER only (quietly) and waits.
 * Three huge icons, no text, so it works for someone who cannot read.
 */
export default function CheckPanel({
  result,
  busy,
  onUp,
  onDown,
}: {
  result: TranslateResult;
  busy: boolean;
  onUp: () => void;
  onDown: () => void;
}) {
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
        aria-label="Hear Echo's guess again"
        className="flex h-24 w-24 items-center justify-center rounded-full border-4 border-primary text-primary transition active:scale-95 disabled:opacity-50"
      >
        <Volume2 aria-hidden className="h-12 w-12" strokeWidth={2.5} />
      </button>
      <div className="grid w-full max-w-md grid-cols-2 gap-4">
        <button
          type="button"
          onClick={onDown}
          disabled={busy}
          aria-label="No, that is wrong"
          data-testid="check-down"
          className="flex aspect-square items-center justify-center rounded-3xl bg-danger text-white shadow-lg transition active:scale-95 disabled:opacity-50"
        >
          <ThumbsDown aria-hidden className="h-20 w-20" strokeWidth={2.5} />
        </button>
        <button
          type="button"
          onClick={onUp}
          disabled={busy}
          aria-label="Yes, that is right"
          data-testid="check-up"
          className="flex aspect-square items-center justify-center rounded-3xl bg-success text-white shadow-lg transition active:scale-95 disabled:opacity-50"
        >
          <ThumbsUp aria-hidden className="h-20 w-20" strokeWidth={2.5} />
        </button>
      </div>
    </div>
  );
}
