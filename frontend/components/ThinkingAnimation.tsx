/** "Echo is thinking": a moving sound wave. No text, so nobody has to read. */
export default function ThinkingAnimation() {
  return (
    <div role="status" aria-label="Thinking" className="flex h-40 items-center justify-center gap-3" data-testid="thinking">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="w-5 rounded-full bg-primary motion-safe:animate-[wave_1s_ease-in-out_infinite]"
          style={{ height: "40%", animationDelay: `${i * 0.12}s` }}
        />
      ))}
    </div>
  );
}
