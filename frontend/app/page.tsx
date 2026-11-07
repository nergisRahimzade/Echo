import { redirect } from "next/navigation";

/** The conversation screen is Echo's home. */
export default function Home() {
  redirect("/talk");
}
