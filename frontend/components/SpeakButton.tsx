"use client";

import { Volume2 } from "lucide-react";
import type { Language } from "@/lib/api";
import { sayAloud } from "@/lib/voice";
import { useT } from "@/lib/i18n";

/** A round speaker icon that reads `text` aloud in Echo's voice, so nobody has to read it. */
export default function SpeakButton({
  text,
  language,
  label,
  size = "md",
}: {
  text: string;
  language: Language;
  label?: string;
  size?: "md" | "lg";
}) {
  const t = useT();
  const text_label = label ?? t("common.readAloud");
  const dims = size === "lg" ? "h-20 w-20" : "h-16 w-16";
  const icon = size === "lg" ? "h-10 w-10" : "h-8 w-8";
  return (
    <button
      type="button"
      aria-label={text_label}
      title={text_label}
      onClick={() => void sayAloud(text, language)}
      className={`${dims} flex shrink-0 items-center justify-center rounded-full border-2 border-primary text-primary transition active:scale-95 focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-primary`}
    >
      <Volume2 aria-hidden className={icon} strokeWidth={2.5} />
    </button>
  );
}
