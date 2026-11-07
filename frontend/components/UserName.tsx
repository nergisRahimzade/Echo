"use client";

import { UserRound } from "lucide-react";
import { useUser } from "@/components/UserGate";

/** The signed-in user's name with a person icon. */
export default function UserName() {
  const user = useUser();
  return (
    <p className="flex items-center gap-2 text-2xl font-semibold" data-testid="user-name">
      <UserRound aria-hidden className="h-8 w-8 text-primary" />
      {user.name}
    </p>
  );
}
