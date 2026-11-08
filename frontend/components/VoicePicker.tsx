"use client";

import { useEffect, useState } from "react";
import { Loader2, Volume2 } from "lucide-react";
import { useUser } from "@/components/UserGate";
import { getVoices, updateUser, type VoiceKind, type VoiceList } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { loadUser, saveUser } from "@/lib/user";
import { sayAloud, setVoice } from "@/lib/voice";

const KIND_ICON: Record<VoiceKind, string> = { woman: "👩", man: "👨", girl: "👧", boy: "👦" };

/** Settings: choose the voice Echo speaks with. Tapping a voice saves it and plays a sample. */
export default function VoicePicker() {
  const { t, lang } = useI18n();
  const user = useUser();
  const [list, setList] = useState<VoiceList | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [selected, setSelected] = useState<string | undefined>(user.voice);
  const [saveFailed, setSaveFailed] = useState(false);

  useEffect(() => {
    getVoices()
      .then((v) => {
        setList(v);
        setSelected((s) => (s && v.voices.some((x) => x.id === s) ? s : v.default));
      })
      .catch(() => setLoadFailed(true));
  }, []);

  const choose = (voice: string) => {
    setSelected(voice);
    setSaveFailed(false);
    setVoice(voice);
    void sayAloud(t("settings.voiceSample"), lang, { voice });
    updateUser(user.user_id, { voice })
      .then(() => {
        const saved = loadUser();
        if (saved) saveUser({ ...saved, voice });
      })
      .catch(() => setSaveFailed(true));
  };

  return (
    <section className="flex flex-col gap-3" aria-labelledby="voice-heading" data-guide="settings-voice">
      <h2 id="voice-heading" className="text-xl font-semibold">
        {t("settings.voice")}
      </h2>

      {loadFailed && (
        <p role="alert" className="text-danger">
          {t("settings.voiceLoadError")}
        </p>
      )}
      {!list && !loadFailed && <Loader2 aria-label={t("common.loading")} className="h-10 w-10 animate-spin text-muted" />}
      {list && !list.enabled && <p className="text-muted">{t("settings.voiceUnavailable")}</p>}

      {list?.enabled && (
        <div className="grid grid-cols-1 gap-3 min-[400px]:grid-cols-2" role="radiogroup" aria-labelledby="voice-heading">
          {list.voices.map((v) => {
            const on = selected === v.id;
            return (
              <button
                key={v.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => choose(v.id)}
                data-testid={`voice-${v.id}`}
                className={`flex min-h-24 items-center gap-3 rounded-2xl border-4 px-4 py-3 text-left transition active:scale-95 ${
                  on ? "border-primary bg-primary/10" : "border-border bg-surface"
                }`}
              >
                <span className="text-4xl" aria-hidden>
                  {KIND_ICON[v.kind]}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-lg font-semibold">{v.name}</span>
                  <span className="text-muted">
                    {t(`settings.voiceKinds.${v.kind}`)} · {t(`settings.voiceStyles.${v.style}`)}
                  </span>
                </span>
                {on && <Volume2 aria-hidden className="h-7 w-7 shrink-0 text-primary" />}
              </button>
            );
          })}
        </div>
      )}
      {list?.enabled && list.missing.length > 0 && <p className="text-muted">{t("settings.voiceChildrenMissing")}</p>}
      {saveFailed && (
        <p role="alert" className="text-danger">
          {t("settings.voiceSaveError")}
        </p>
      )}
    </section>
  );
}
