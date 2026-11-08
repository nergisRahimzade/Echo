"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { currentTheme, setTheme, type Theme } from "@/lib/theme";
import { useT } from "@/lib/i18n";

const OPTIONS: { theme: Theme; Icon: typeof Sun }[] = [
  { theme: "light", Icon: Sun },
  { theme: "dark", Icon: Moon },
];

/** Settings: switch between the light and the dark colours. */
export default function ThemeToggle() {
  const t = useT();
  const [theme, setThemeState] = useState<Theme | null>(null);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- the theme is only readable in the browser
  useEffect(() => setThemeState(currentTheme()), []);

  const choose = (next: Theme) => {
    setTheme(next);
    setThemeState(next);
  };

  return (
    <section className="flex flex-col gap-3" aria-labelledby="theme-heading" data-guide="settings-theme">
      <h2 id="theme-heading" className="text-xl font-semibold">
        {t("settings.theme")}
      </h2>
      <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-labelledby="theme-heading">
        {OPTIONS.map(({ theme: option, Icon }) => {
          const on = theme === option;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => choose(option)}
              data-testid={`theme-${option}`}
              className={`flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border-4 transition active:scale-95 ${
                on ? "border-primary bg-primary/10" : "border-border bg-surface"
              }`}
            >
              <Icon aria-hidden className="h-9 w-9" />
              <span className="text-lg font-semibold">{t(option === "light" ? "settings.themeLight" : "settings.themeDark")}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
