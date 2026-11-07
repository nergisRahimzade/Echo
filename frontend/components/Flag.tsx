/**
 * Small inline SVG flags. (Flag emojis don't render on Windows, so we draw them.)
 * To add a language, add its flag here.
 */

export type FlagCode = "tr" | "gb";

export default function Flag({ code, className = "h-9 w-14" }: { code: FlagCode; className?: string }) {
  if (code === "tr") {
    return (
      <svg viewBox="0 0 30 20" className={`${className} rounded-md shadow-sm`} aria-hidden>
        <rect width="30" height="20" fill="#E30A17" />
        <circle cx="11" cy="10" r="5" fill="#fff" />
        <circle cx="12.25" cy="10" r="4" fill="#E30A17" />
        <polygon
          fill="#fff"
          points="16.5,10 19.9,8.9 17.8,11.8 17.8,8.2 19.9,11.1"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 60 30" className={`${className} rounded-md shadow-sm`} aria-hidden>
      <clipPath id="gb-clip">
        <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
      </clipPath>
      <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" clipPath="url(#gb-clip)" stroke="#C8102E" strokeWidth="4" />
      <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  );
}
