import EnrollFlow from "@/components/EnrollFlow";
import Header from "@/components/Header";
import MainNav from "@/components/MainNav";
import UserGate from "@/components/UserGate";

export default function EnrollPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <MainNav current="/enroll" />
      </Header>
      <UserGate>
        <main className="flex flex-1 flex-col">
          <EnrollFlow />
        </main>
      </UserGate>
    </div>
  );
}
