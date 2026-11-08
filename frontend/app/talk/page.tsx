import Header from "@/components/Header";
import MainNav from "@/components/MainNav";
import TalkScreen from "@/components/TalkScreen";
import UsageGuide from "@/components/UsageGuide";
import UserGate from "@/components/UserGate";

export default function TalkPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <MainNav current="/talk" />
      </Header>
      <UserGate>
        <main className="flex flex-1 flex-col">
          <TalkScreen />
        </main>
        <UsageGuide page="talk" />
      </UserGate>
    </div>
  );
}
