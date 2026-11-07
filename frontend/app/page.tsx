import { Mic } from "lucide-react";
import Header from "@/components/Header";
import HealthBadge from "@/components/HealthBadge";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <HealthBadge />
      </Header>
      <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10">
        {/* Placeholder: recording is wired up in task 1.3 */}
        <button
          type="button"
          aria-label="Hold to talk"
          className="flex min-h-[160px] w-full max-w-md flex-col items-center justify-center gap-3 rounded-3xl bg-primary px-6 py-8 text-primary-foreground shadow-lg transition active:scale-95 focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-primary"
        >
          <Mic aria-hidden className="h-16 w-16" strokeWidth={2.5} />
          <span className="text-2xl font-semibold">Hold to talk</span>
        </button>
      </main>
    </div>
  );
}
