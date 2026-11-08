import Header from "@/components/Header";
import MainNav from "@/components/MainNav";
import UsageGuide from "@/components/UsageGuide";
import UserGate from "@/components/UserGate";
import WordsManager from "@/components/WordsManager";

export default function WordsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <MainNav current="/words" />
      </Header>
      <UserGate>
        <main className="flex flex-1 flex-col">
          <WordsManager />
        </main>
        <UsageGuide page="words" />
      </UserGate>
    </div>
  );
}
