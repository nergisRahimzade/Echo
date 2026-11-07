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
    <nav className="flex gap-2" aria-label="Main">
      {ITEMS.map(({ href, label, Icon }) => (
        <Link
          key={href}
          href={href}
          aria-label={t(label)}
          title={t(label)}
          aria-current={current === href ? "page" : undefined}
          className={`flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-2xl border-2 transition active:scale-95 ${
            current === href ? "border-primary bg-primary/10 text-primary" : "border-border"
          }`}
        >
          <Icon aria-hidden className="h-7 w-7 sm:h-8 sm:w-8" />
        </Link>
      ))}
    </nav>
  );
}
