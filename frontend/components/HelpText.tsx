import SpeakButton from "@/components/SpeakButton";
import type { Language } from "@/lib/api";

/** A short instruction on screen, with a speaker button so people who can't read it can hear it. */
export default function HelpText({ text, language, testId }: { text: string; language: Language; testId?: string }) {
  return (
    <div className="flex w-full max-w-md items-center justify-center gap-3" data-testid={testId}>
      <p className="text-center text-lg leading-snug">{text}</p>
      <SpeakButton text={text} language={language} />
    </div>
  );
}
