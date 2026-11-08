"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, MessageSquarePlus, Repeat, RotateCcw } from "lucide-react";
import CheckPanel from "@/components/CheckPanel";
import CountdownThumbDown from "@/components/CountdownThumbDown";
import HealthBadge from "@/components/HealthBadge";
import HelpText from "@/components/HelpText";
import HelperFix from "@/components/HelperFix";
import HelperTurnInput from "@/components/HelperTurnInput";
import HoldToRecord from "@/components/HoldToRecord";
import LearningRing from "@/components/LearningRing";
import ListenerView from "@/components/ListenerView";
import ThinkingAnimation from "@/components/ThinkingAnimation";
import { useUser } from "@/components/UserGate";
import { ApiError, sendFeedback, translate, type TranslateResult } from "@/lib/api";
import { playPrompt } from "@/lib/prompts";
import { currentSessionId, startNewSession } from "@/lib/session";
import type { Recording } from "@/lib/useRecorder";
import { loadVoice, sayAloud } from "@/lib/voice";
import { useI18n } from "@/lib/i18n";

/** How long the thumbs-down stays after Echo speaks on its own. */
const UNDO_SECONDS = 5;

type Stage =
  | { kind: "idle" }
  | { kind: "thinking" }
  | { kind: "spoken"; result: TranslateResult; undo: boolean } // said aloud; undo = thumbs-down still offered
  | { kind: "check"; result: TranslateResult; busy: boolean } // played privately, waiting for 👍 / 👎
  | { kind: "repeat"; result: TranslateResult } // wrong guess: say it again
  | { kind: "helper"; result: TranslateResult } // second wrong guess: a helper types it
  | { kind: "error"; message: string };

/**
 * The main screen the user talks through.
 * Icons only for the user; large text only for the listener.
 */
export default function TalkScreen() {
  const user = useUser();
  const { t, lang: uiLang } = useI18n();
  const [sessionId, setSessionId] = useState<string>("");
  const [stage, setStage] = useState<Stage>({ kind: "idle" });
  const [learnedKey, setLearnedKey] = useState(0); // bump after each approval to refresh the ring
  const learnedOne = () => setLearnedKey((k) => k + 1);
  // true after the first 👎: the user is saying it again, and one more 👎 brings the helper.
  const [lastTry, setLastTry] = useState(false);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- sessionStorage is only readable after mount
  useEffect(() => setSessionId(currentSessionId()), []);

  const showError = useCallback(
    (err: unknown) => setStage({ kind: "error", message: err instanceof ApiError ? err.message : t("common.somethingWrong") }),
    [t],
  );

  /** Say it aloud for the listener. `undo` offers the 5-second thumbs-down (only when Echo decided alone). */
  const speakToListener = useCallback((result: TranslateResult, undo = true) => {
    if (!undo) setLastTry(false); // a sentence the user approved: the next one starts fresh
    setStage({ kind: "spoken", result, undo });
    void sayAloud(result.sentence, result.language);
  }, []);

  /** Wrong guess: ask the user to say it again, in their language. */
  const askToRepeat = useCallback((result: TranslateResult) => {
    setLastTry(true);
    setStage({ kind: "repeat", result });
    void playPrompt("sayAgain", uiLang); // prompts are for the user: in the app language
  }, [uiLang]);

  /** Second wrong guess in a row: stop guessing, offer the helper. */
  const callHelper = useCallback((result: TranslateResult) => {
    setLastTry(false);
    setStage({ kind: "helper", result });
    void playPrompt("helper", uiLang);
  }, [uiLang]);

  const afterThumbsDown = (result: TranslateResult, nextAction: string) =>
    nextAction === "helper" ? callHelper(result) : askToRepeat(result);

  const onRecorded = useCallback(
    async (rec: Recording) => {
      setStage({ kind: "thinking" });
      try {
        const result = await translate({ userId: user.user_id, sessionId, audio: rec.blob });
        // Fetch the sentence's audio while "thinking" is still shown, so the buttons and the
        // voice appear together and the guess plays at once (no tap on the speaker needed).
        await loadVoice(result.sentence, result.language);
        if (result.action === "speak") speakToListener(result);
        else setStage({ kind: "check", result, busy: false });
      } catch (err) {
        showError(err);
      }
    },
    [user.user_id, sessionId, speakToListener, showError],
  );

  // ----- after Echo spoke on its own -----
  async function flagSpokenAsWrong(result: TranslateResult) {
    try {
      const { next_action } = await sendFeedback({ utteranceId: result.utterance_id, verdict: "down" });
      afterThumbsDown(result, next_action);
    } catch (err) {
      showError(err);
    }
  }

  // ----- the private check -----
  async function checkAnswer(result: TranslateResult, verdict: "up" | "down") {
    setStage({ kind: "check", result, busy: true });
    try {
      const { next_action } = await sendFeedback({ utteranceId: result.utterance_id, verdict });
      if (next_action === "speak") {
        speakToListener(result, false); // the user approved it: no undo needed
        learnedOne();
      } else afterThumbsDown(result, next_action);
    } catch (err) {
      showError(err);
    }
  }

  async function confirmSpoken(result: TranslateResult) {
    setStage({ kind: "spoken", result, undo: false });
    try {
      await sendFeedback({ utteranceId: result.utterance_id, verdict: "up", auto: true });
      learnedOne();
    } catch {
      /* the sentence was already said; a missed confirmation only costs one learning example */
    }
  }

  /** The helper typed what was meant: save it as a correction, then say it aloud. */
  async function submitHelperFix(result: TranslateResult, text: string) {
    try {
      await sendFeedback({ utteranceId: result.utterance_id, verdict: "down", finalText: text });
      speakToListener({ ...result, sentence: text }, false);
      learnedOne();
    } catch (err) {
      showError(err);
    }
  }

  const newConversation = () => {
    setSessionId(startNewSession());
    setLastTry(false);
    setStage({ kind: "idle" });
  };

  const showRecorder = stage.kind === "idle" || stage.kind === "error" || stage.kind === "repeat" || (stage.kind === "spoken" && !stage.undo);

  return (
    
<div className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-6">
  <div className="flex flex-col gap-2 text-center">
    <span className="text-xs font-semibold uppercase tracking-[0.25em] text-primary">
      {stage.kind === "spoken" ? "Listener Mode" : "User Mode"}
    </span>
    <h2 className="text-3xl font-bold tracking-tight text-foreground">
      {stage.kind === "spoken"
        ? "Here's what I said"
        : stage.kind === "thinking"
          ? "Understanding your voice"
          : "Your voice matters"}
    </h2>
  </div>

      {/* The screen is icon-only on purpose; screen readers still get a page heading. */}
      <h1 className="sr-only">{t("talk.heading")}</h1>
      {/* Listener area: large text, only ever shows sentences that were said aloud */}
      <section className="flex min-h-48 flex-1 flex-col items-center justify-center gap-6" aria-live="polite">
        {stage.kind === "idle" && <HelpText text={t("talk.intro")} language={uiLang} testId="talk-intro" />}

        {stage.kind === "thinking" && <ThinkingAnimation />}

        {stage.kind === "spoken" && (
          <>
           
<div className="w-full rounded-3xl border-2 border-primary/30 bg-surface px-6 py-10 text-center shadow-lg">
  <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-primary">
    Your message
  </p>
  <p
    className="text-3xl font-bold leading-relaxed text-foreground sm:text-5xl"
    lang={stage.result.language}
    data-testid="listener-sentence"
  >
    {stage.result.sentence}
  </p>
</div>

            {!stage.undo && <ListenerView sentence={stage.result.sentence} language={stage.result.language} />}
            {stage.undo && (
              <CountdownThumbDown
                seconds={UNDO_SECONDS}
                lastTry={lastTry}
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
            lastTry={lastTry}
            onUp={() => checkAnswer(stage.result, "up")}
            onDown={() => checkAnswer(stage.result, "down")}
          />
        )}

        {stage.kind === "repeat" && (
          <div className="flex flex-col items-center gap-3" data-testid="repeat-prompt">
            <span className="flex h-28 w-28 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Repeat aria-label={t("talk.sayAgain")} className="h-14 w-14" />
            </span>
          </div>
        )}

        {stage.kind === "helper" && <HelperFix onSubmit={(text) => submitHelperFix(stage.result, text)} />}

        {stage.kind === "error" && (
          <div role="alert" className="flex flex-col items-center gap-3 text-center">
            <AlertTriangle aria-hidden className="h-16 w-16 text-danger" />
            <p className="text-lg text-muted">{stage.message}</p>
            <button
              type="button"
              onClick={() => setStage({ kind: "idle" })}
              aria-label={t("common.tryAgain")}
              className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-border"
            >
              <RotateCcw aria-hidden className="h-8 w-8" />
            </button>
          </div>
        )}
      </section>

      

{/* User Mode: show recording controls only when needed */}
{showRecorder && sessionId && stage.kind !== "spoken" && (
  <section className="flex w-full flex-col items-center gap-4 rounded-3xl border border-border bg-surface p-5 shadow-lg">
    <span className="text-xs font-semibold uppercase tracking-widest text-primary">
      {stage.kind === "repeat"
        ? "Try speaking again"
        : "Your voice, your way"}
    </span>

    <HoldToRecord onRecorded={onRecorded} />
  </section>
)}


      <div className="flex flex-wrap items-center justify-center gap-3">
        {sessionId && <HelperTurnInput userId={user.user_id} sessionId={sessionId} />}
        <button
          type="button"
          onClick={newConversation}
          aria-label={t("talk.newConversation")}
          title={t("talk.newConversation")}
          className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-border bg-surface transition active:scale-95"
        >
          <MessageSquarePlus aria-hidden className="h-8 w-8" />
        </button>
        <LearningRing userId={user.user_id} refreshKey={learnedKey} />
        <HealthBadge />
      </div>
    </div>
  );
}
