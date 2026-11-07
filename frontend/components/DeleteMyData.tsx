"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, Trash2 } from "lucide-react";
import SpeakButton from "@/components/SpeakButton";
import { useUser } from "@/components/UserGate";
import { deleteUserData } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { clearUser } from "@/lib/user";
import { setVoice } from "@/lib/voice";

type Stage = "idle" | "confirm" | "deleting" | "deleted" | "error";

/** Settings: delete everything Echo stores about the user. Two steps, so one tap can't do it. */
export default function DeleteMyData() {
  const { t, lang } = useI18n();
  const user = useUser();
  const [stage, setStage] = useState<Stage>("idle");

  const remove = async () => {
    setStage("deleting");
    try {
      await deleteUserData(user.user_id);
      clearUser();
      setVoice(undefined);
      try {
        window.sessionStorage.removeItem("echo.session");
      } catch {
        /* storage blocked */
      }
      setStage("deleted");
    } catch {
      setStage("error");
    }
  };

  const button = "flex min-h-16 items-center justify-center gap-3 rounded-2xl px-5 text-lg font-semibold transition active:scale-95";

  return (
    <section className="flex flex-col gap-3" aria-labelledby="privacy-heading">
      <h2 id="privacy-heading" className="text-xl font-semibold">
        {t("settings.privacy")}
      </h2>
      <div className="flex items-start gap-3">
        <p className="flex-1 text-muted">{t("settings.deleteHelp")}</p>
        <SpeakButton text={t("settings.deleteHelp")} language={lang} />
      </div>

      {stage === "idle" || stage === "error" ? (
        <button
          type="button"
          onClick={() => setStage("confirm")}
          data-testid="delete-data"
          className={`${button} border-4 border-danger text-danger`}
        >
          <Trash2 aria-hidden className="h-7 w-7" />
          {t("settings.deleteAll")}
        </button>
      ) : null}

      {stage === "confirm" && (
        <div className="flex flex-col gap-3 rounded-2xl border-4 border-danger p-4" role="group" aria-label={t("settings.deleteAll")}>
          <button
            type="button"
            onClick={() => setStage("idle")}
            autoFocus
            data-testid="delete-cancel"
            className={`${button} border-4 border-border bg-surface`}
          >
            {t("settings.deleteCancel")}
          </button>
          <button type="button" onClick={remove} data-testid="delete-confirm" className={`${button} bg-danger text-danger-foreground`}>
            <Trash2 aria-hidden className="h-7 w-7" />
            {t("settings.deleteConfirm")}
          </button>
        </div>
      )}

      {stage === "deleting" && (
        <p role="status" className="flex items-center gap-3 text-lg">
          <Loader2 aria-hidden className="h-7 w-7 animate-spin" />
          {t("settings.deleting")}
        </p>
      )}

      {stage === "deleted" && (
        <div className="flex flex-col gap-3" data-testid="delete-done">
          <p role="status" className="flex items-center gap-3 text-lg font-semibold">
            <CheckCircle2 aria-hidden className="h-8 w-8 text-primary" />
            {t("settings.deleted")}
          </p>
          <Link href="/onboarding" className={`${button} bg-primary text-primary-foreground`}>
            {t("settings.startOver")}
          </Link>
        </div>
      )}

      {stage === "error" && (
        <p role="alert" className="text-danger">
          {t("settings.deleteError")}
        </p>
      )}
    </section>
  );
}
