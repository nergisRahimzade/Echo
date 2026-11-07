"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import Header from "@/components/Header";
import { getDemoUser } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { saveUser } from "@/lib/user";
import { setVoice } from "@/lib/voice";

/** /demo: sign in as the ready-trained demo account (scripts/seed_demo.py) and go to the talk screen. */
export default function DemoPage() {
  const router = useRouter();
  const t = useT();
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    getDemoUser()
      .then((u) => {
        saveUser({ user_id: u.user_id, name: u.name, main_language: u.main_language, voice: u.voice });
        setVoice(u.voice);
        router.replace("/talk");
      })
      .catch(() => setMissing(true));
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-6 px-4 py-8 text-center">
        {missing ? (
          <>
            <h1 className="text-2xl font-semibold">{t("demo.missing")}</h1>
            <Link
              href="/onboarding"
              className="flex min-h-16 items-center justify-center rounded-2xl bg-primary px-6 text-lg font-semibold text-primary-foreground transition active:scale-95"
            >
              {t("demo.signUp")}
            </Link>
          </>
        ) : (
          <>
            <h1 className="sr-only">{t("demo.loading")}</h1>
            <Loader2 aria-label={t("demo.loading")} className="h-12 w-12 animate-spin text-muted" />
          </>
        )}
      </main>
    </div>
  );
}
