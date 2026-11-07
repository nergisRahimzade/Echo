"use client";

import Link from "next/link";
import { AudioLines, MessageCircle, Settings, UsersRound } from "lucide-react";
import { useT } from "@/lib/i18n";

const ITEMS = [
  { href: "/talk", label: "nav.talk", Icon: MessageCircle },
  { href: "/enroll", label: "nav.enroll", Icon: AudioLines },
  { href: "/words", label: "nav.words", Icon: UsersRound },
  { href: "/settings", label: "nav.settings", Icon: Settings },
];

/** Icon-only navigation in the header. `current` marks the page you're on. */
export default function MainNav({ current }: { current?: string }) {
  const t = useT();
  return (
    <nav className="flex gap-1.5 sm:gap-2" aria-label={t("nav.main")}>
      {ITEMS.map(({ href, label, Icon }) => (
        <Link
          key={href}
          href={href}
          aria-label={t(label)}
          title={t(label)}
          aria-current={current === href ? "page" : undefined}
          className={`flex h-16 w-16 items-center justify-center rounded-2xl border-2 transition active:scale-95 ${
            current === href ? "border-primary bg-primary/10 text-primary" : "border-border"
          }`}
        >
          <Icon aria-hidden className="h-8 w-8" />
        </Link>
      ))}
    </nav>
  );
}
