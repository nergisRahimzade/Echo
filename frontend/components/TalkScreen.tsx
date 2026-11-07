"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, MessageSquarePlus, Repeat, RotateCcw } from "lucide-react";
import CheckPanel from "@/components/CheckPanel";
import CountdownThumbDown from "@/components/CountdownThumbDown";
import HealthBadge from "@/components/HealthBadge";
import HelperTurnInput from "@/components/HelperTurnInput";
import HoldToRecord from "@/components/HoldToRecord";
import ThinkingAnimation from "@/components/ThinkingAnimation";
import { useUser } from "@/components/UserGate";
import { ApiError, sendFeedback, translate, type TranslateResult } from "@/lib/api";
import { playPrompt } from "@/lib/prompts";
import { currentSessionId, startNewSession } from "@/lib/session";
import type { Recording } from "@/lib/useRecorder";
import { sayAloud } from "@/lib/voice";

/** How long the thumbs-down stays after Echo speaks on its own. */
const UNDO_SECONDS = 5;

type Stage =
  | { kind: "idle" }
  | { kind: "thinking" }
  | { kind: "spoken"; result: TranslateResult; undo: boolean } // said aloud; undo = thumbs-down still offered
  | { kind: "check"; result: TranslateResult; busy: boolean } // played privately, waiting for 👍 / 👎
  | { kind: "repeat"; result: TranslateResult } // wrong guess: say it again
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

  const showError = (err: unknown) =>
    setStage({ kind: "error", message: err instanceof ApiError ? err.message : "Something went wrong." });

  /** Say it aloud for the listener. `undo` offers the 5-second thumbs-down (only when Echo decided alone). */
  const speakToListener = useCallback((result: TranslateResult, undo = true) => {
    setStage({ kind: "spoken", result, undo });
    void sayAloud(result.sentence, result.language);
  }, []);

  /** Wrong guess: ask the user to say it again, in their language. */
  const askToRepeat = useCallback((result: TranslateResult) => {
    setStage({ kind: "repeat", result });
    void playPrompt("sayAgain", result.language);
  }, []);

  const onRecorded = useCallback(
    async (rec: Recording) => {
      setStage({ kind: "thinking" });
      try {
        const result = await translate({ userId: user.user_id, sessionId, audio: rec.blob });
        if (result.action === "speak") speakToListener(result);
        else setStage({ kind: "check", result, busy: false });
      } catch (err) {
        showError(err);
      }
    },
    [user.user_id, sessionId, speakToListener],
  );

  // ----- after Echo spoke on its own -----
  async function flagSpokenAsWrong(result: TranslateResult) {
    try {
      await sendFeedback({ utteranceId: result.utterance_id, verdict: "down" });
      askToRepeat(result);
    } catch (err) {
      showError(err);
    }
  }

  // ----- the private check -----
  async function checkAnswer(result: TranslateResult, verdict: "up" | "down") {
    setStage({ kind: "check", result, busy: true });
    try {
      const { next_action } = await sendFeedback({ utteranceId: result.utterance_id, verdict });
      if (next_action === "speak") speakToListener(result, false); // the user approved it: no undo needed
      else askToRepeat(result);
    } catch (err) {
      showError(err);
    }
  }

  async function confirmSpoken(result: TranslateResult) {
    setStage({ kind: "spoken", result, undo: false });
    try {
      await sendFeedback({ utteranceId: result.utterance_id, verdict: "up", auto: true });
    } catch {
      /* the sentence was already said; a missed confirmation only costs one learning example */
    }
  }

  const newConversation = () => {
    setSessionId(startNewSession());
    setStage({ kind: "idle" });
  };

  const showRecorder = stage.kind === "idle" || stage.kind === "error" || stage.kind === "repeat" || (stage.kind === "spoken" && !stage.undo);

  return (
    <div className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-6">
      {/* Listener area: large text, only ever shows sentences that were said aloud */}
      <section className="flex min-h-48 flex-1 flex-col items-center justify-center gap-6" aria-live="polite">
        {stage.kind === "thinking" && <ThinkingAnimation />}

        {stage.kind === "spoken" && (
          <>
            <p className="text-center text-4xl font-bold leading-tight sm:text-5xl" lang={stage.result.language} data-testid="listener-sentence">
              {stage.result.sentence}
            </p>
            {stage.undo && (
              <CountdownThumbDown
                seconds={UNDO_SECONDS}
                onDown={() => flagSpokenAsWrong(stage.result)}
                onExpire={() => confirmSpoken(stage.result)}
              />
            )}
          </>
        )}

        {stage.kind === "check" && (
          <CheckPanel
            result={stage.result}
            busy={stage.busy}
            onUp={() => checkAnswer(stage.result, "up")}
            onDown={() => checkAnswer(stage.result, "down")}
          />
        )}

        {stage.kind === "repeat" && (
          <div className="flex flex-col items-center gap-3" data-testid="repeat-prompt">
            <span className="flex h-28 w-28 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Repeat aria-label="Say it again" className="h-14 w-14" />
            </span>
          </div>
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

      {/* User area: the big button */}
      <section className="flex flex-col items-center gap-4">
        {showRecorder && <HoldToRecord onRecorded={onRecorded} disabled={!sessionId} />}
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
