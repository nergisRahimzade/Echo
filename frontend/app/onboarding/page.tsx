"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, Loader2 } from "lucide-react";
import Flag, { type FlagCode } from "@/components/Flag";
import Header from "@/components/Header";
import SpeakButton from "@/components/SpeakButton";
import { ApiError, createUser } from "@/lib/api";
import { saveUser, speakingLanguage, type MainLanguage } from "@/lib/user";
import { translate, useI18n } from "@/lib/i18n";

const LANGUAGES: { value: MainLanguage; flags: FlagCode[]; label: string }[] = [
  { value: "tr", flags: ["tr"], label: "Türkçe" },
  { value: "en", flags: ["gb"], label: "English" },
  { value: "both", flags: ["tr", "gb"], label: "both" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { t, lang: uiLang, setLang } = useI18n();
  const [name, setName] = useState("");
  const [language, setLanguage] = useState<MainLanguage>("tr");
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const speakLang = speakingLanguage({ main_language: language });
  // Picking a language switches the whole screen to it right away.
  const chooseLanguage = (value: MainLanguage) => {
    setLanguage(value);
    setLang(speakingLanguage({ main_language: value }), false);
  };
  const consentText = translate(speakLang, "onboarding.consent");
  const canSubmit = name.trim().length > 0 && consent && !saving;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      const { user_id } = await createUser(name.trim(), language, consent);
      saveUser({ user_id, name: name.trim(), main_language: language });
      setLang(uiLang); // remember the interface language that was used to sign up
      router.replace("/enroll"); // next step: teach Echo your voice
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWrong"));
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-8 px-4 py-8">
        <div>
          <h1 className="text-3xl font-bold">{t("onboarding.title")}</h1>
          <p className="mt-2 text-lg text-muted">{t("onboarding.helperNote")}</p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-8">
          {/* Name */}
          <label className="flex flex-col gap-2">
            <span className="text-xl font-semibold">{t("onboarding.name")}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={60}
              autoComplete="given-name"
              className="min-h-16 rounded-2xl border-2 border-border bg-surface px-4 text-2xl outline-none focus:border-primary"
            />
          </label>

          {/* Main language */}
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-xl font-semibold">{t("onboarding.language")}</legend>
            <div className="grid grid-cols-3 gap-3">
              {LANGUAGES.map((l) => {
                const selected = language === l.value;
                return (
                  <button
                    key={l.value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => chooseLanguage(l.value)}
                    className={`flex min-h-28 flex-col items-center justify-center gap-1 rounded-2xl border-4 px-2 py-3 transition active:scale-95 ${
                      selected ? "border-primary bg-primary/10" : "border-border bg-surface"
                    }`}
                  >
                    <span className="flex gap-1">
                      {l.flags.map((f) => (
                        <Flag key={f} code={f} className={l.flags.length > 1 ? "h-7 w-10" : "h-9 w-14"} />
                      ))}
                    </span>
                    <span className="text-center text-base font-semibold">{l.label === "both" ? t("onboarding.both") : l.label}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Consent */}
          <div className="flex flex-col gap-4 rounded-2xl border-2 border-border bg-surface p-4">
            <div className="flex items-start gap-4">
              <p className="flex-1 text-lg leading-relaxed">{consentText}</p>
              <SpeakButton text={consentText} language={speakLang} label={t("onboarding.consentAloud")} />
            </div>
            <button
              type="button"
              role="checkbox"
              aria-checked={consent}
              onClick={() => setConsent((c) => !c)}
              className={`flex min-h-16 items-center gap-4 rounded-2xl border-4 px-4 text-xl font-semibold transition active:scale-[0.98] ${
                consent ? "border-success bg-success/10" : "border-border"
              }`}
            >
              <span
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border-4 ${
                  consent ? "border-success bg-success text-success-foreground" : "border-muted"
                }`}
              >
                {consent && <Check aria-hidden className="h-7 w-7" strokeWidth={3.5} />}
              </span>
              {translate(speakLang, "onboarding.agree")}
            </button>
          </div>

          {error && (
            <p role="alert" className="rounded-2xl border-2 border-danger p-4 text-lg text-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            aria-label={t("onboarding.continue")}
            className="flex min-h-20 items-center justify-center gap-3 rounded-3xl bg-primary text-2xl font-semibold text-primary-foreground shadow-lg transition active:scale-95 disabled:opacity-40"
          >
            {saving ? (
              <Loader2 aria-hidden className="h-9 w-9 animate-spin" />
            ) : (
              <ArrowRight aria-hidden className="h-9 w-9" strokeWidth={2.5} />
            )}
          </button>
        </form>
      </main>
    </div>
  );
}
