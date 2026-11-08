"use client";

import DeleteMyData from "@/components/DeleteMyData";
import Flag from "@/components/Flag";
import ThemeToggle from "@/components/ThemeToggle";
import VoicePicker from "@/components/VoicePicker";
import { UI_LANGUAGES, useI18n } from "@/lib/i18n";

/** Settings: the app language and Echo's voice and deleting all of the user's data. */
export default function SettingsPanel() {
  const { t, lang, setLang } = useI18n();

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-8 px-4 py-6">
      <h1 className="text-3xl font-bold">{t("settings.title")}</h1>

      <section className="flex flex-col gap-3" aria-labelledby="lang-heading" data-guide="settings-language">
        <h2 id="lang-heading" className="text-xl font-semibold">
          {t("settings.language")}
        </h2>
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-labelledby="lang-heading">
          {UI_LANGUAGES.map((l) => (
            <button
              key={l.code}
              type="button"
              role="radio"
              aria-checked={lang === l.code}
              onClick={() => setLang(l.code)}
              data-testid={`ui-lang-${l.code}`}
              className={`flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border-4 transition active:scale-95 ${
                lang === l.code ? "border-primary bg-primary/10" : "border-border bg-surface"
              }`}
            >
              <Flag code={l.flag} />
              <span className="text-lg font-semibold">{l.name}</span>
            </button>
          ))}
        </div>
      </section>

      <ThemeToggle />

      <VoicePicker />

      <DeleteMyData />
    </div>
  );
}
