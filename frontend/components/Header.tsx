import { AudioLines } from "lucide-react";

/** Top bar shown on every screen: the Echo logo and name. */
export default function Header({ children }: { children?: React.ReactNode }) {
  return (
    <header className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3 sm:px-6">
      <div className="flex items-center gap-2">
        <AudioLines aria-hidden className="h-8 w-8 shrink-0 text-primary" strokeWidth={2.5} />
        {/* On narrow phones only the logo shows, so the four 64 px nav icons fit. */}
        <span className="sr-only text-2xl font-bold tracking-tight min-[440px]:not-sr-only">Echo</span>
      </div>
      {children}
    </header>
  );
}
