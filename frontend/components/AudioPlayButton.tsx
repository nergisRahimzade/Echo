"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { useT } from "@/lib/i18n";

/** A big round play/pause icon for a recorded clip. */
export default function AudioPlayButton({ blob, label }: { blob: Blob; label?: string }) {
  const t = useT();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const u = URL.createObjectURL(blob);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- object URL must be created/revoked with the blob
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [blob]);

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) audio.pause();
    else {
      audio.currentTime = 0;
      void audio.play();
    }
  };

  return (
    <>
      {url && (
        <audio
          ref={audioRef}
          src={url}
          preload="auto"
          data-testid="recording-audio"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
        />
      )}
      <button
        type="button"
        aria-label={playing ? t("common.pause") : (label ?? t("common.play"))}
        onClick={toggle}
        className="flex h-20 w-20 items-center justify-center rounded-full bg-success text-white shadow-md transition active:scale-95"
      >
        {playing ? <Pause aria-hidden className="h-10 w-10" /> : <Play aria-hidden className="ml-1 h-10 w-10" />}
      </button>
    </>
  );
}
