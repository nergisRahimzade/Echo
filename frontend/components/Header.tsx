import { AudioLines } from "lucide-react";

/** Top bar shown on every screen: the Echo logo and name. */
export default function Header({ children }: { children?: React.ReactNode }) {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-border bg-surface px-4 py-3 sm:px-6">
      <div className="flex items-center gap-2">
        <AudioLines aria-hidden className="h-8 w-8 text-primary" strokeWidth={2.5} />
        <span className="text-2xl font-bold tracking-tight">Echo</span>
      </div>
      {children}
    </header>
  );
}
