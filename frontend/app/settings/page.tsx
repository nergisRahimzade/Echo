import Header from "@/components/Header";
import MainNav from "@/components/MainNav";
import SettingsPanel from "@/components/SettingsPanel";
import UsageGuide from "@/components/UsageGuide";
import UserGate from "@/components/UserGate";

export default function SettingsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header>
        <MainNav current="/settings" />
      </Header>
      <UserGate>
        <main className="flex flex-1 flex-col">
          <SettingsPanel />
        </main>
        <UsageGuide tour="settings" />
      </UserGate>
    </div>
  );
}
