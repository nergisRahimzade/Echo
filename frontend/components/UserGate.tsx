"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { ApiError, getUser } from "@/lib/api";
import { clearUser, loadUser, saveUser, type SavedUser } from "@/lib/user";
import { useT } from "@/lib/i18n";
import { setVoice } from "@/lib/voice";

const UserContext = createContext<SavedUser | null>(null);

/** The signed-in user, for any component inside <UserGate>. */
export function useUser(): SavedUser {
  const user = useContext(UserContext);
  if (!user) throw new Error("useUser must be used inside <UserGate>");
  return user;
}

/**
 * Shows its children only when a user is signed up in this browser.
 * No saved user, or one the server no longer knows -> go to onboarding.
 * Server unreachable -> keep the saved user (don't sign people out over bad Wi-Fi).
 */
export default function UserGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const t = useT();
  const [user, setUser] = useState<SavedUser | null>(null);

  useEffect(() => {
    const saved = loadUser();
    if (!saved) {
      router.replace("/onboarding");
      return;
    }
    // Show the screen immediately, then confirm with the server in the background.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is only readable after mount
    setUser(saved);
    setVoice(saved.voice);
    getUser(saved.user_id)
      .then((fresh) => {
        const updated = {
          user_id: fresh.user_id,
          name: fresh.name,
          main_language: fresh.main_language,
          voice: fresh.voice,
        };
        saveUser(updated);
        setVoice(updated.voice);
        setUser(updated);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          clearUser();
          router.replace("/onboarding");
        }
      });
  }, [router]);

  if (!user) {
    return (
      <div className="flex flex-1 items-center justify-center" aria-busy="true">
        <Loader2 aria-label={t("common.loading")} className="h-12 w-12 animate-spin text-muted" />
      </div>
    );
  }
  return <UserContext.Provider value={user}>{children}</UserContext.Provider>;
}
