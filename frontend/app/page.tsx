import Header from "@/components/Header";
import HealthBadge from "@/components/HealthBadge";
import HomeRecorder from "@/components/HomeRecorder";
import UserGate from "@/components/UserGate";
import UserName from "@/components/UserName";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <HealthBadge />
      </Header>
      <UserGate>
        <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10">
          <UserName />
          <HomeRecorder />
        </main>
      </UserGate>
    </div>
  );
}
