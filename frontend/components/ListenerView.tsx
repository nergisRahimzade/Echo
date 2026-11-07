"use client";

import { useEffect, useState } from "react";
import { FlipVertical2, Maximize2 } from "lucide-react";
import { useT } from "@/lib/i18n";

/**
 * "Show to listener": fills the whole screen with the sentence so the other person can read it.
 * Tap anywhere to close. The flip icon turns it 180° for someone sitting opposite.
 */
export default function ListenerView({ sentence, language }: { sentence: string; language: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("talk.showListener")}
        title={t("talk.showListener")}
        data-testid="show-listener"
        className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-border bg-surface transition active:scale-95"
      >
        <Maximize2 aria-hidden className="h-8 w-8" />
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t("talk.listenerDialog")}
          data-testid="listener-view"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 flex cursor-pointer items-center justify-center bg-background p-6"
        >
          <p
            lang={language}
            className="text-center text-6xl font-bold leading-tight break-words sm:text-7xl"
            style={{ transform: flipped ? "rotate(180deg)" : undefined, transition: "transform 0.3s" }}
          >
            {sentence}
          </p>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation(); // flipping must not close the view
              setFlipped((f) => !f);
            }}
            aria-label={t("talk.flip")}
            aria-pressed={flipped}
            data-testid="flip-listener"
            className="absolute bottom-6 right-6 flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-border bg-surface"
          >
            <FlipVertical2 aria-hidden className="h-8 w-8" />
          </button>
        </div>
      )}
    </>
  );
}
