"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AudioLines, CircleHelp, Volume2, X } from "lucide-react";
import {
  findTarget,
  markTourSeen,
  markWelcomed,
  PAGES,
  setGuideOpen,
  tourSeen,
  visibleSteps,
  welcomed,
  type GuidePlace,
  type GuideStep,
  type PageId,
  type StepId,
} from "@/lib/guide";
import { sayAloud, stopVoice } from "@/lib/voice";
import { useI18n } from "@/lib/i18n";

const EDGE = 16; // keep the bubble this far from the screen edges
const GAP = 20; // space between the spotlight and the bubble
const ARROW = 14;

type Phase = "closed" | "welcome" | "steps";
type Box = { left: number; top: number; width: number; height: number };
type Layout = { spot: Box; vw: number; vh: number; bw: number; bh: number };
type Placed = { left: number; top: number; side: GuidePlace | "free"; arrow: number };

/** Where the bubble goes: the step's preferred side if it fits, else any side that fits, else the bottom of the screen. */
function placeBubble({ spot, vw, vh, bw, bh }: Layout, preferred: GuidePlace): Placed {
  const cx = spot.left + spot.width / 2;
  const cy = spot.top + spot.height / 2;
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, Math.max(lo, hi)));
  const fits: Record<GuidePlace, boolean> = {
    bottom: spot.top + spot.height + GAP + bh <= vh - EDGE,
    top: spot.top - GAP - bh >= EDGE,
    right: spot.left + spot.width + GAP + bw <= vw - EDGE,
    left: spot.left - GAP - bw >= EDGE,
  };
  const order: GuidePlace[] = [preferred, "bottom", "top", "right", "left"];
  const side = order.find((s) => fits[s]);
  if (side === "bottom" || side === "top") {
    const left = clamp(cx - bw / 2, EDGE, vw - EDGE - bw);
    const top = side === "bottom" ? spot.top + spot.height + GAP : spot.top - GAP - bh;
    return { left, top, side, arrow: clamp(cx - left - ARROW / 2, 20, bw - 20 - ARROW) };
  }
  if (side === "right" || side === "left") {
    const top = clamp(cy - bh / 2, EDGE, vh - EDGE - bh);
    const left = side === "right" ? spot.left + spot.width + GAP : spot.left - GAP - bw;
    return { left, top, side, arrow: clamp(cy - top - ARROW / 2, 20, bh - 20 - ARROW) };
  }
  // Nothing fits (a big element on a small screen): sit at the bottom of the screen, no arrow.
  return { left: clamp((vw - bw) / 2, EDGE, vw - EDGE - bw), top: vh - EDGE - bh, side: "free", arrow: 0 };
}

function arrowStyle(p: Placed): React.CSSProperties | null {
  const half = -ARROW / 2;
  switch (p.side) {
    case "bottom":
      return { top: half, left: p.arrow };
    case "top":
      return { bottom: half, left: p.arrow };
    case "right":
      return { left: half, top: p.arrow };
    case "left":
      return { right: half, top: p.arrow };
    default:
      return null;
  }
}

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * The usage guide for one page. It dims the screen, lights up one control at a time and explains
 * it in a bubble next to it (every bubble can be read aloud):
 * - the page tour: by itself on the first visit, and from the "How to use Echo" button,
 *   covering every control that is on screen at that moment;
 * - moment tours: once, the first time a control that appears later shows up (Echo's guess,
 *   the undo ring, the helper box, the enroll review buttons, a saved word...).
 */
export default function UsageGuide({ page }: { page: PageId }) {
  const { t, lang } = useI18n();
  const guide = PAGES[page];
  const [phase, setPhase] = useState<Phase>("closed");
  const [tourId, setTourId] = useState<string>(page);
  const [steps, setSteps] = useState<GuideStep[]>([]);
  const [index, setIndex] = useState(0);
  const [layout, setLayout] = useState<Layout | null>(null);
  const bubbleRef = useRef<HTMLDivElement>(null);
  const primaryRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const spokeRef = useRef(false);

  const begin = useCallback((id: string, ids: StepId[], withWelcome: boolean) => {
    const list = visibleSteps(ids);
    if (list.length === 0) return;
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setTourId(id);
    setSteps(list);
    setIndex(0);
    setLayout(null);
    setPhase(withWelcome ? "welcome" : "steps");
  }, []);

  // First visit: the page tour starts by itself once the page has loaded (its main control is on screen).
  useEffect(() => {
    if (tourSeen(page)) return;
    let tries = 0;
    let settle: ReturnType<typeof setTimeout> | undefined;
    const poll = setInterval(() => {
      tries += 1;
      const ready = findTarget(PAGES[page].ready) !== null;
      if (!ready && tries < 75) return;
      clearInterval(poll);
      // Give the rest of the page a moment to appear (status pill, progress ring).
      if (ready) settle = setTimeout(() => begin(page, PAGES[page].steps, !welcomed()), 400);
    }, 200);
    return () => {
      clearInterval(poll);
      clearTimeout(settle);
    };
  }, [page, begin]);

  // Moment tours: watch for controls that appear later, once the page tour has been seen.
  useEffect(() => {
    if (phase !== "closed" || guide.moments.length === 0) return;
    const watch = setInterval(() => {
      if (!tourSeen(page)) return;
      const moment = guide.moments.find((m) => !tourSeen(m.id) && findTarget(m.ready) !== null);
      if (moment) begin(moment.id, moment.steps, false);
    }, 400);
    return () => clearInterval(watch);
  }, [phase, page, guide, begin]);

  // While a bubble is open, page timers (the 5-second undo ring) wait for it.
  useEffect(() => {
    setGuideOpen(phase !== "closed");
    return () => setGuideOpen(false);
  }, [phase]);

  const step = phase === "steps" ? steps[index] : undefined;

  // Follow the lit-up element: bring it into view, then track its box (scrolling, resizing, layout changes).
  useEffect(() => {
    if (!step) return;
    const el = findTarget(step.target);
    if (!el) return;
    const pad = step.pad ?? 0;
    el.scrollIntoView({ block: "center", inline: "nearest", behavior: reducedMotion() ? "auto" : "smooth" });
    let frame = 0;
    let last = "";
    const tick = () => {
      const r = el.getBoundingClientRect();
      const bw = bubbleRef.current?.offsetWidth ?? 0;
      const bh = bubbleRef.current?.offsetHeight ?? 0;
      const key = [r.left, r.top, r.width, r.height, window.innerWidth, window.innerHeight, bw, bh].join();
      if (key !== last) {
        last = key;
        setLayout({
          spot: { left: r.left - pad, top: r.top - pad, width: r.width + pad * 2, height: r.height + pad * 2 },
          vw: document.documentElement.clientWidth,
          vh: window.innerHeight,
          bw,
          bh,
        });
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [step]);

  // Keyboard and switch users land on the main button of each bubble.
  useEffect(() => {
    if (phase !== "closed") primaryRef.current?.focus({ preventScroll: true });
  }, [phase, index]);

  const silence = () => {
    if (spokeRef.current) stopVoice();
    spokeRef.current = false;
  };

  const close = () => {
    silence();
    markTourSeen(tourId);
    markWelcomed();
    // Moments whose controls were just explained don't need their own tour later.
    const shown = new Set(steps.map((s) => s.target));
    guide.moments.forEach((m) => shown.has(m.ready) && markTourSeen(m.id));
    setPhase("closed");
    setLayout(null);
    openerRef.current?.focus({ preventScroll: true });
  };

  const go = (next: number) => {
    silence();
    if (next >= steps.length) return close();
    setIndex(Math.max(0, next));
  };

  const startTour = () => {
    markWelcomed();
    setPhase("steps");
  };

  const speak = (text: string) => {
    spokeRef.current = true;
    void sayAloud(text, lang);
  };

  // Escape closes; Tab stays inside the bubble while it is open.
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key !== "Tab") return;
    const items = Array.from(e.currentTarget.querySelectorAll<HTMLElement>("button"));
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const title = step ? t(`guide.steps.${step.id}.title`) : "";
  const body = step ? t(`guide.steps.${step.id}.body`) : "";
  const placed = step && layout && layout.bw > 0 ? placeBubble(layout, step.place ?? "bottom") : null;
  const arrow = placed ? arrowStyle(placed) : null;
  const animate = typeof window !== "undefined" && !reducedMotion();

  // Bubble controls keep a dark focus ring: the page's ring colour is too light on the light bubble in dark mode.
  const card = "bg-guide-card text-guide-ink [&_button:focus-visible]:outline-guide-accent";
  const iconButton = "flex h-11 w-11 items-center justify-center rounded-xl transition hover:bg-guide-line/50 active:scale-95";
  const secondary = "min-h-12 rounded-xl border border-guide-line px-4 text-[15px] font-medium transition active:scale-95";
  const primary = "min-h-12 rounded-xl bg-guide-accent px-[18px] text-[15px] font-semibold text-guide-accent-ink transition active:scale-95";

  return (
    <>
      {/* Keeps the last controls of the page from sitting under the button below. */}
      <div aria-hidden className="h-24 shrink-0" />
      <button
        type="button"
        onClick={() => begin(page, guide.steps, false)}
        data-guide="guide-button"
        data-testid="guide-open"
        className="fixed bottom-4 right-4 z-40 flex min-h-14 items-center gap-2.5 rounded-full border-2 border-border bg-surface pl-3.5 pr-5 text-base font-medium shadow-md transition active:scale-95 sm:bottom-6 sm:right-6"
      >
        <CircleHelp aria-hidden className="h-6 w-6 text-primary" />
        {t("guide.open")}
      </button>

      {phase !== "closed" && (
        <>
          {/* Blocks taps on the page while the guide is open, and keeps focus in the bubble. */}
          <div aria-hidden className="fixed inset-0 z-[60]" onMouseDown={(e) => e.preventDefault()} />

          {/* The dimmed screen with a clear, ringed hole over the element being explained. */}
          {placed && layout ? (
            <div
              aria-hidden
              data-testid="guide-spotlight"
              className={`pointer-events-none fixed z-[61] ${animate ? "transition-all duration-200 ease-out" : ""}`}
              style={{
                ...layout.spot,
                borderRadius: (step?.radius ?? 16) === 999 ? 999 : (step?.radius ?? 16) + (step?.pad ?? 0),
                boxShadow:
                  "0 0 0 4px var(--guide-ring), 0 0 0 12px var(--guide-ring-soft), 0 0 0 200vmax var(--guide-dim)",
              }}
            />
          ) : (
            <div aria-hidden className="pointer-events-none fixed inset-0 z-[61]" style={{ background: "var(--guide-dim)" }} />
          )}

          {phase === "welcome" && (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="guide-welcome-title"
              aria-describedby="guide-welcome-body"
              onKeyDown={onKeyDown}
              data-testid="guide-welcome"
              className={`fixed left-1/2 top-1/2 z-[62] w-[min(420px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-3xl p-8 text-center shadow-[0_24px_60px_rgba(0,0,0,0.55)] ${card}`}
            >
              <button
                type="button"
                onClick={() => speak(`${t("guide.welcomeTitle")}. ${t("guide.welcomeBody")}`)}
                aria-label={t("guide.readAloud")}
                title={t("guide.readAloud")}
                className={`absolute right-3 top-3 text-guide-accent ${iconButton}`}
              >
                <Volume2 aria-hidden className="h-6 w-6" />
              </button>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-[18px] bg-guide-accent text-guide-accent-ink">
                <AudioLines aria-hidden className="h-9 w-9" strokeWidth={2.2} />
              </div>
              <h2 id="guide-welcome-title" className="mb-2 text-[26px] font-bold">
                {t("guide.welcomeTitle")}
              </h2>
              <p id="guide-welcome-body" className="mb-6 text-[17px] leading-[1.45] text-guide-muted">
                {t("guide.welcomeBody")}
              </p>
              <div className="flex flex-wrap justify-center gap-2.5">
                <button type="button" onClick={close} className={`${secondary} min-h-[52px] px-[22px] text-base`}>
                  {t("guide.skip")}
                </button>
                <button
                  ref={primaryRef}
                  type="button"
                  onClick={startTour}
                  data-testid="guide-start"
                  className={`${primary} min-h-[52px] px-[26px] text-base`}
                >
                  {t("guide.start")}
                </button>
              </div>
            </div>
          )}

          {phase === "steps" && step && (
            <div
              ref={bubbleRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="guide-title"
              aria-describedby="guide-body"
              onKeyDown={onKeyDown}
              data-testid="guide-bubble"
              data-step={step.id}
              className={`fixed z-[62] w-[min(320px,calc(100vw-32px))] rounded-[18px] p-5 text-left shadow-[0_18px_50px_rgba(0,0,0,0.5)] ${card} ${
                animate ? "transition-[left,top] duration-200 ease-out" : ""
              }`}
              // Measured invisibly first, then moved next to its element. Opacity, not visibility:
              // a hidden element can't take focus, and keyboard users must land on "Next".
              style={placed ? { left: placed.left, top: placed.top } : { left: 0, top: 0, opacity: 0 }}
            >
              {arrow && <div aria-hidden className="absolute h-3.5 w-3.5 rotate-45 bg-guide-card" style={arrow} />}
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-[0.06em] text-guide-accent">
                  {t("guide.stepOf", { n: index + 1, total: steps.length })}
                </span>
                <div className="-mr-2 flex">
                  <button
                    type="button"
                    onClick={() => speak(`${title}. ${body}`)}
                    aria-label={t("guide.readAloud")}
                    title={t("guide.readAloud")}
                    className={`text-guide-accent ${iconButton}`}
                  >
                    <Volume2 aria-hidden className="h-5 w-5" />
                  </button>
                  <button
                    type="button"
                    onClick={close}
                    aria-label={t("guide.close")}
                    title={t("guide.close")}
                    data-testid="guide-close"
                    className={`text-guide-muted ${iconButton}`}
                  >
                    <X aria-hidden className="h-5 w-5" />
                  </button>
                </div>
              </div>
              <h2 id="guide-title" className="mb-1.5 text-xl font-semibold">
                {title}
              </h2>
              <p id="guide-body" className="mb-[18px] text-base leading-[1.45] text-guide-muted">
                {body}
              </p>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div aria-hidden className="flex gap-1">
                  {steps.map((s, i) => (
                    <span
                      key={s.id}
                      className={`block h-1.5 rounded-full ${i === index ? "w-4 bg-guide-accent" : "w-1.5 bg-guide-line"}`}
                    />
                  ))}
                </div>
                <div className="ml-auto flex gap-2">
                  {index > 0 && (
                    <button type="button" onClick={() => go(index - 1)} data-testid="guide-back" className={secondary}>
                      {t("guide.back")}
                    </button>
                  )}
                  <button ref={primaryRef} type="button" onClick={() => go(index + 1)} data-testid="guide-next" className={primary}>
                    {index === steps.length - 1 ? t("guide.finish") : t("guide.next")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
