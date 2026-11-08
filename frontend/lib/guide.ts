/**
 * The usage guide: one short tour per page. Each step points at an element marked with
 * data-guide="<target>" and explains it in a bubble (texts: locales, guide.steps.<id>).
 * Steps whose element is not on screen (another stage of the page, a hidden feature) are skipped.
 */

export type GuidePlace = "bottom" | "top" | "right" | "left";
export type TourId = "talk" | "enroll" | "words" | "settings";

export interface GuideStep {
  /** Key under guide.steps in the locales. */
  id: string;
  /** The data-guide value of the element to spotlight. */
  target: string;
  /** Preferred side for the bubble; it moves to another side when there is no room. */
  place?: GuidePlace;
  /** Corner radius of the element (999 for round things); the ring follows it. Default 16. */
  radius?: number;
  /** Extra room between the element and the ring, for elements without a border of their own. Default 0. */
  pad?: number;
}

const NAV: GuideStep[] = [
  { id: "navTalk", target: "nav-talk", place: "bottom" },
  { id: "navEnroll", target: "nav-enroll", place: "bottom" },
  { id: "navWords", target: "nav-words", place: "bottom" },
  { id: "navSettings", target: "nav-settings", place: "bottom" },
];

const GUIDE_BUTTON: GuideStep = { id: "guideButton", target: "guide-button", place: "top", radius: 999 };

export const TOURS: Record<TourId, GuideStep[]> = {
  talk: [
    ...NAV,
    { id: "talkRecord", target: "record", place: "right", radius: 24 },
    { id: "newConversation", target: "new-conversation", place: "top" },
    { id: "learned", target: "learned", place: "top", radius: 999 },
    { id: "health", target: "health", place: "top", radius: 999 },
    GUIDE_BUTTON,
  ],
  enroll: [
    { id: "enrollProgress", target: "enroll-progress", place: "right", radius: 999 },
    { id: "enrollLanguage", target: "enroll-language", place: "bottom", pad: 4 },
    { id: "enrollStart", target: "enroll-start", place: "right", radius: 999 },
    { id: "enrollPhrase", target: "enroll-phrase", place: "bottom", pad: 8 },
    { id: "enrollSkip", target: "enroll-skip", place: "bottom", radius: 999 },
    { id: "enrollRecord", target: "record", place: "right", radius: 24 },
    { id: "enrollFinished", target: "enroll-finished-actions", place: "top", radius: 999, pad: 8 },
    GUIDE_BUTTON,
  ],
  words: [
    { id: "wordsTabs", target: "words-tabs", place: "bottom" },
    { id: "wordsAdd", target: "words-add", place: "bottom" },
    { id: "wordsRecord", target: "words-record", place: "left", radius: 999 },
    GUIDE_BUTTON,
  ],
  settings: [
    { id: "settingsLanguage", target: "settings-language", place: "bottom", pad: 12 },
    { id: "settingsTheme", target: "settings-theme", place: "bottom", pad: 12 },
    { id: "settingsVoice", target: "settings-voice", place: "top", pad: 12 },
    { id: "settingsPrivacy", target: "settings-privacy", place: "top", pad: 12 },
    GUIDE_BUTTON,
  ],
};

const SEEN_PREFIX = "echo.guide.";
const WELCOMED_KEY = "echo.guide.welcomed";

function read(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return true; // storage blocked: don't pop the guide up on every page load
  }
}

function write(key: string): void {
  try {
    window.localStorage.setItem(key, "1");
  } catch {
    /* storage blocked */
  }
}

/** Has this page's tour been shown (finished or closed) before? */
export const tourSeen = (tour: TourId) => read(SEEN_PREFIX + tour);
export const markTourSeen = (tour: TourId) => write(SEEN_PREFIX + tour);
/** The welcome card is shown once, before the very first tour. */
export const welcomed = () => read(WELCOMED_KEY);
export const markWelcomed = () => write(WELCOMED_KEY);

export function findTarget(target: string): HTMLElement | null {
  const el = document.querySelector<HTMLElement>(`[data-guide="${target}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 ? el : null;
}
