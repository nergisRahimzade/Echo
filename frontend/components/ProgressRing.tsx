/** A circular progress indicator with a count in the middle (e.g. 7 / 20). */
export default function ProgressRing({
  done,
  total,
  size = 72,
  label,
}: {
  done: number;
  total: number;
  size?: number;
  label?: string;
}) {
  const stroke = size / 9;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const fraction = total > 0 ? Math.min(1, done / total) : 0;
  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={done}
      aria-label={label ?? `${done} of ${total}`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--success)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - fraction)}
          className="transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-mono text-sm font-semibold tabular-nums">
        {done}/{total}
      </span>
    </div>
  );
}
