"use client";

import { useEffect, useState } from "react";
import { Database, Server } from "lucide-react";
import { getHealth, type Health } from "@/lib/api";
import { useT } from "@/lib/i18n";

type State = { kind: "loading" } | { kind: "ok"; health: Health } | { kind: "down" };

/** Small status pill in the header: is the server up, is the database connected. */
export default function HealthBadge() {
  const t = useT();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      getHealth()
        .then((health) => !cancelled && setState({ kind: "ok", health }))
        .catch(() => !cancelled && setState({ kind: "down" }));
    check();
    const timer = setInterval(check, 15000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const serverUp = state.kind === "ok";
  const dbUp = state.kind === "ok" && state.health.db === "connected";
  const label =
    state.kind === "loading"
      ? t("health.checking")
      : !serverUp
        ? t("health.offline")
        : dbUp
          ? t("health.ok")
          : t("health.dbProblem", { db: state.health.db });

  return (
    <div
      role="status"
      aria-label={label}
      title={label}
      className="flex items-center gap-3 rounded-full border border-border px-3 py-1.5 text-sm"
    >
      <Dot icon={<Server aria-hidden className="h-4 w-4" />} on={serverUp} loading={state.kind === "loading"} />
      <Dot icon={<Database aria-hidden className="h-4 w-4" />} on={dbUp} loading={state.kind === "loading"} />
      <span className="hidden sm:inline text-muted">{label}</span>
    </div>
  );
}

function Dot({ icon, on, loading }: { icon: React.ReactNode; on: boolean; loading: boolean }) {
  const color = loading ? "bg-muted" : on ? "bg-success" : "bg-danger";
  return (
    <span className="flex items-center gap-1">
      {icon}
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
    </span>
  );
}
