"use client";

import { useEffect, useRef, useState } from "react";
import { ThumbsDown } from "lucide-react";
import { useT } from "@/lib/i18n";

/**
 * A big thumbs-down that stays for `seconds` with a shrinking ring around it.
 * Tap = "that's wrong". Time runs out = the sentence counts as right.
 */
export default function CountdownThumbDown({
  seconds = 5,
  lastTry = false,
  onDown,
  onExpire,
}: {
  seconds?: number;
  /** The user already said one guess was wrong: the next 👎 brings the helper's keyboard. */
  lastTry?: boolean;
  onDown: () => void;
  onExpire: () => void;
}) {
  const t = useT();
  const [left, setLeft] = useState(seconds);
  const done = useRef(false);
  const expire = useRef(onExpire);
  useEffect(() => {
    expire.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    const started = performance.now();
    const timer = setInterval(() => {
      const remaining = Math.max(0, seconds - (performance.now() - started) / 1000);
      setLeft(remaining);
      if (remaining <= 0 && !done.current) {
        done.current = true;
        clearInterval(timer);
        expire.current();
      }
    }, 100);
    return () => clearInterval(timer);
  }, [seconds]);

  const size = 128;
  const r = 58;
  const c = 2 * Math.PI * r;
  return (
    <div className="flex max-w-xs flex-col items-center gap-3">
      <button
        type="button"
        aria-label={t("talk.wrong")}
        aria-describedby="countdown-help"
        data-testid="thumbs-down-countdown"
        onClick={() => {
          if (done.current) return;
          done.current = true;
          onDown();
        }}
        className="relative flex items-center justify-center rounded-full transition active:scale-95"
        style={{ width: size, height: size }}
      >
        <svg width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="8" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--danger)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - left / seconds)}
          />
        </svg>
        <span className="flex h-24 w-24 items-center justify-center rounded-full bg-danger text-danger-foreground">
          <ThumbsDown aria-hidden className="h-12 w-12" strokeWidth={2.5} />
        </span>
      </button>
      <p id="countdown-help" className="text-center leading-snug" data-testid="countdown-help">
        {t(lastTry ? "talk.downHelpLast" : "talk.downHelp")}
      </p>
    </div>
  );
}
