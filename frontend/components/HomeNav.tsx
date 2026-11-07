import Link from "next/link";
import { AudioLines, UsersRound } from "lucide-react";

/** Big icon shortcuts on the home screen. */
export default function HomeNav() {
  return (
    <nav className="flex justify-center gap-4" aria-label="Main">
      <NavIcon href="/enroll" label="Teach Echo your voice" icon={<AudioLines aria-hidden className="h-9 w-9" />} />
      <NavIcon href="/words" label="Names and places" icon={<UsersRound aria-hidden className="h-9 w-9" />} />
    </nav>
  );
}

function NavIcon({ href, label, icon }: { href: string; label: string; icon: React.ReactNode }) {
  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      className="flex h-20 w-20 items-center justify-center rounded-2xl border-2 border-border bg-surface shadow-sm transition active:scale-95"
    >
      {icon}
    </Link>
  );
}
