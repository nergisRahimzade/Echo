import Link from "next/link";
import { House } from "lucide-react";
import Header from "@/components/Header";
import UserGate from "@/components/UserGate";
import WordsManager from "@/components/WordsManager";

export default function WordsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <Link href="/" aria-label="Home" className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-border">
          <House aria-hidden className="h-8 w-8" />
        </Link>
      </Header>
      <UserGate>
        <main className="flex flex-1 flex-col">
          <WordsManager />
        </main>
      </UserGate>
    </div>
  );
}
