"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, MessageSquarePlus, RotateCcw } from "lucide-react";
import HealthBadge from "@/components/HealthBadge";
import HelperTurnInput from "@/components/HelperTurnInput";
import HoldToRecord from "@/components/HoldToRecord";
import ThinkingAnimation from "@/components/ThinkingAnimation";
import { useUser } from "@/components/UserGate";
import { ApiError, translate, type TranslateResult } from "@/lib/api";
import { currentSessionId, startNewSession } from "@/lib/session";
import type { Recording } from "@/lib/useRecorder";

type Stage =
  | { kind: "idle" }
  | { kind: "thinking" }
  | { kind: "result"; result: TranslateResult }
  | { kind: "error"; message: string };

/**
 * The main screen the user talks through.
 * Icons only for the user; large text only for the listener.
 */
export default function TalkScreen() {
  const user = useUser();
  const [sessionId, setSessionId] = useState<string>("");
  const [stage, setStage] = useState<Stage>({ kind: "idle" });

  // eslint-disable-next-line react-hooks/set-state-in-effect -- sessionStorage is only readable after mount
  useEffect(() => setSessionId(currentSessionId()), []);

  const onRecorded = useCallback(
    async (rec: Recording) => {
      setStage({ kind: "thinking" });
      try {
        const result = await translate({ userId: user.user_id, sessionId, audio: rec.blob });
        setStage({ kind: "result", result });
      } catch (err) {
        setStage({ kind: "error", message: err instanceof ApiError ? err.message : "Something went wrong." });
      }
    },
    [user.user_id, sessionId],
  );

  const newConversation = () => {
    setSessionId(startNewSession());
    setStage({ kind: "idle" });
  };

  return (
    <div className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-6">
      {/* Listener area */}
      <section className="flex min-h-48 flex-1 flex-col items-center justify-center" aria-live="polite">
        {stage.kind === "thinking" && <ThinkingAnimation />}
        {stage.kind === "result" && (
          <p
            className="text-center text-4xl font-bold leading-tight sm:text-5xl"
            lang={stage.result.language}
            data-testid="listener-sentence"
            data-action={stage.result.action}
          >
            {stage.result.sentence}
          </p>
        )}
        {stage.kind === "error" && (
          <div role="alert" className="flex flex-col items-center gap-3 text-center">
            <AlertTriangle aria-hidden className="h-16 w-16 text-danger" />
            <p className="text-lg text-muted">{stage.message}</p>
            <button
              type="button"
              onClick={() => setStage({ kind: "idle" })}
              aria-label="Try again"
              className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-border"
            >
              <RotateCcw aria-hidden className="h-8 w-8" />
            </button>
          </div>
        )}
      </section>

      {/* User area: the big button (hidden while thinking so it can't be pressed twice) */}
      <section className="flex flex-col items-center gap-4">
        {stage.kind !== "thinking" && <HoldToRecord onRecorded={onRecorded} disabled={!sessionId} />}
      </section>

      <div className="flex items-center justify-center gap-3">
        {sessionId && <HelperTurnInput userId={user.user_id} sessionId={sessionId} />}
        <button
          type="button"
          onClick={newConversation}
          aria-label="Start a new conversation"
          title="Start a new conversation"
          className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-border bg-surface transition active:scale-95"
        >
          <MessageSquarePlus aria-hidden className="h-8 w-8" />
        </button>
        <HealthBadge />
      </div>
    </div>
  );
}
