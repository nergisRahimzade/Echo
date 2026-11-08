"use client";

import { useEffect, useState } from "react";
import { Sprout } from "lucide-react";
import { getProgress, type Progress } from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * How much Echo has learned: a ring that fills as approved sentences grow (toward the next
 * milestone), with the number next to it for helpers ("42 sentences learned").
 * Pass a new `refreshKey` after each approval to update it.
 */
export default function LearningRing({ userId, refreshKey = 0 }: { userId: string; refreshKey?: number }) {
  const t = useT();
  const [progress, setProgress] = useState<Progress | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProgress(userId)
      .then((p) => !cancelled && setProgress(p))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  const learned = progress?.learned ?? 0;
  const fraction = progress?.fraction ?? 0;
  const size = 64;
  const r = 27;
  const c = 2 * Math.PI * r;
  const label = t("talk.learned", { n: learned });

  return (
    <div className="flex items-center gap-2" role="img" aria-label={label} title={label} data-testid="learning-ring" data-learned={learned} data-guide="learned">
      <span className="relative flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="7" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--success)"
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - fraction)}
            className="transition-[stroke-dashoffset] duration-700"
            data-testid="learning-ring-arc"
          />
        </svg>
        <Sprout aria-hidden className="h-7 w-7 text-success" />
      </span>
      <span className="font-mono text-lg font-semibold tabular-nums text-muted" aria-hidden>
        {learned}
      </span>
    </div>
  );
}
