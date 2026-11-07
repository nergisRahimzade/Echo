"use client";

import { useState } from "react";
import AudioPlayButton from "@/components/AudioPlayButton";
import HoldToRecord from "@/components/HoldToRecord";
import type { Recording } from "@/lib/useRecorder";

/** Home screen recorder: record, then play it back. (Translation is wired up in phase 3-4.) */
export default function HomeRecorder() {
  const [last, setLast] = useState<Recording | null>(null);
  return (
    <div className="flex w-full flex-col items-center gap-6">
      <HoldToRecord onRecorded={setLast} />
      {last && (
        <div className="flex items-center gap-4" data-testid="last-recording">
          <AudioPlayButton blob={last.blob} />
          <span className="font-mono text-lg text-muted">{(last.durationMs / 1000).toFixed(1)} s</span>
        </div>
      )}
    </div>
  );
}
