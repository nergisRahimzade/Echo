"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import SpeakButton from "@/components/SpeakButton";
import { useI18n } from "@/lib/i18n";
import { clearUser } from "@/lib/user";
import { setVoice } from "@/lib/voice";

/**
 * Settings: forget the user on this device and go back to the sign-up page.
 * Nothing is deleted on the server, but Echo has no log-in yet, so this browser can't get back
 * into the account afterwards: two steps, so one tap can't do it.
 */
export default function SignOut() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);

  const signOut = () => {
    clearUser();
    setVoice(undefined);
    try {
      window.sessionStorage.removeItem("echo.session"); // the current conversation
    } catch {
      /* storage blocked */
    }
    router.replace("/onboarding");
  };

  const button = "flex min-h-16 items-center justify-center gap-3 rounded-2xl px-5 text-lg font-semibold transition active:scale-95";

  return (
    <section className="flex flex-col gap-3" aria-labelledby="signout-heading" data-guide="settings-signout">
      <h2 id="signout-heading" className="text-xl font-semibold">
        {t("settings.signOut")}
      </h2>
      <div className="flex items-start gap-3">
        <p className="flex-1 text-muted">{t("settings.signOutHelp")}</p>
        <SpeakButton text={t("settings.signOutHelp")} language={lang} />
      </div>

      {confirming ? (
        <div className="flex flex-col gap-3 rounded-2xl border-4 border-primary p-4" role="group" aria-label={t("settings.signOut")}>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            autoFocus
            data-testid="signout-cancel"
            className={`${button} border-4 border-border bg-surface`}
          >
            {t("settings.signOutCancel")}
          </button>
          <button type="button" onClick={signOut} data-testid="signout-confirm" className={`${button} bg-primary text-primary-foreground`}>
            <LogOut aria-hidden className="h-7 w-7" />
            {t("settings.signOutConfirm")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          data-testid="signout"
          className={`${button} border-4 border-border bg-surface`}
        >
          <LogOut aria-hidden className="h-7 w-7" />
          {t("settings.signOut")}
        </button>
      )}
    </section>
  );
}
