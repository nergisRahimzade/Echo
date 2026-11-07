import Link from "next/link";
import { AudioLines, MessageCircle, UsersRound } from "lucide-react";

const ITEMS = [
  { href: "/talk", label: "Talk", Icon: MessageCircle },
  { href: "/enroll", label: "Teach Echo your voice", Icon: AudioLines },
  { href: "/words", label: "Names and places", Icon: UsersRound },
];

/** Icon-only navigation in the header. `current` marks the page you're on. */
export default function MainNav({ current }: { current?: string }) {
  return (
    <nav className="flex gap-2" aria-label="Main">
      {ITEMS.map(({ href, label, Icon }) => (
        <Link
          key={href}
          href={href}
          aria-label={label}
          title={label}
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
