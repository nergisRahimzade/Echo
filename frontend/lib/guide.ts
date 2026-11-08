/**
 * The usage guide. Every control in Echo has a step: it points at the element marked
 * data-guide="<target>" and explains it in a bubble (texts: locales, guide.steps.<id>).
 *
 * - Each page has a tour of all its steps, in screen order. It runs by itself the first time the
 *   page opens and again from the "How to use Echo" button; steps whose element is not on screen
 *   right now (another stage of the page) are left out.
 * - Controls that only appear later (Echo's guess, the undo ring, the helper box, the enroll review
 *   buttons, a saved word...) have a short "moment" tour that runs once, the first time they appear.
 */

export type GuidePlace = "bottom" | "top" | "right" | "left";
export type PageId = "onboarding" | "talk" | "enroll" | "words" | "settings";

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

const step = (id: string, target: string, place: GuidePlace, more: Partial<GuideStep> = {}): GuideStep => ({
  id,
  target,
  place,
  ...more,
});

export const STEPS = {
  // Header (every signed-in page)
  navTalk: step("navTalk", "nav-talk", "bottom"),
  navEnroll: step("navEnroll", "nav-enroll", "bottom"),
  navWords: step("navWords", "nav-words", "bottom"),
  navSettings: step("navSettings", "nav-settings", "bottom"),
  guideButton: step("guideButton", "guide-button", "top", { radius: 999 }),

  // Sign-up
  onbName: step("onbName", "onboarding-name", "bottom", { pad: 8 }),
  onbLanguage: step("onbLanguage", "onboarding-language", "bottom", { pad: 8 }),
  onbConsent: step("onbConsent", "onboarding-consent", "top"),
  onbAgree: step("onbAgree", "onboarding-agree", "top"),
  onbContinue: step("onbContinue", "onboarding-continue", "top", { radius: 24 }),
  onbDemo: step("onbDemo", "onboarding-demo", "top"),

  // Talk
  checkGuess: step("checkGuess", "check-guess", "bottom", { pad: 8 }),
  checkDown: step("checkDown", "check-down", "bottom", { radius: 24 }),
  checkUp: step("checkUp", "check-up", "bottom", { radius: 24 }),
  spokenSentence: step("spokenSentence", "listener-sentence", "bottom", { pad: 8 }),
  undoDown: step("undoDown", "undo-down", "right", { radius: 999 }),
  writeIt: step("writeIt", "write-it", "top"),
  showListener: step("showListener", "show-listener", "bottom"),
  repeat: step("repeat", "repeat", "bottom", { radius: 999 }),
  helperIcon: step("helperIcon", "helper-icon", "right", { radius: 999 }),
  helperForm: step("helperForm", "helper-form", "bottom", { pad: 8 }),
  writeCancel: step("writeCancel", "write-cancel", "top", { radius: 24 }),
  talkRecord: step("talkRecord", "record", "right", { radius: 24 }),
  newConversation: step("newConversation", "new-conversation", "top"),
  learned: step("learned", "learned", "top", { radius: 999 }),
  health: step("health", "health", "top", { radius: 999 }),

  // Enroll
  enrollProgress: step("enrollProgress", "enroll-progress", "right", { radius: 999 }),
  enrollLanguage: step("enrollLanguage", "enroll-language", "bottom", { pad: 4 }),
  enrollStart: step("enrollStart", "enroll-start", "right", { radius: 999 }),
  enrollPhrase: step("enrollPhrase", "enroll-phrase", "bottom", { pad: 8 }),
  enrollSkip: step("enrollSkip", "enroll-skip", "bottom", { radius: 999 }),
  enrollRecord: step("enrollRecord", "record", "right", { radius: 24 }),
  enrollRedo: step("enrollRedo", "enroll-redo", "top", { radius: 999 }),
  enrollListen: step("enrollListen", "enroll-listen", "top", { radius: 999 }),
  enrollSave: step("enrollSave", "enroll-save", "top", { radius: 999 }),
  enrollFinished: step("enrollFinished", "enroll-finished-actions", "top", { radius: 999, pad: 8 }),

  // Names and places
  wordsTabs: step("wordsTabs", "words-tabs", "bottom"),
  wordsAdd: step("wordsAdd", "words-add", "bottom"),
  wordsRecord: step("wordsRecord", "words-record", "left", { radius: 999 }),
  wordsDelete: step("wordsDelete", "words-delete", "left", { radius: 999 }),

  // Settings
  settingsLanguage: step("settingsLanguage", "settings-language", "bottom", { pad: 12 }),
  settingsTheme: step("settingsTheme", "settings-theme", "bottom", { pad: 12 }),
  settingsVoice: step("settingsVoice", "settings-voice", "top", { pad: 12 }),
  settingsPrivacy: step("settingsPrivacy", "settings-privacy", "top", { pad: 12 }),
} satisfies Record<string, GuideStep>;

export type StepId = keyof typeof STEPS;

/** A short tour that runs once, the first time `ready` appears on screen. */
export interface MomentTour {
  id: string;
  ready: string;
  steps: StepId[];
}

export interface PageGuide {
  /** The element that shows the page has loaded; the page tour waits for it. */
  ready: string;
  /** Every step of the page, in screen order. */
  steps: StepId[];
  moments: MomentTour[];
}

const NAV: StepId[] = ["navTalk", "navEnroll", "navWords", "navSettings"];

export const PAGES: Record<PageId, PageGuide> = {
  onboarding: {
    ready: "onboarding-name",
    steps: ["onbName", "onbLanguage", "onbConsent", "onbAgree", "onbContinue", "onbDemo", "guideButton"],
    moments: [],
  },
  talk: {
    ready: "record",
    steps: [
      ...NAV,
      "checkGuess", "checkDown", "checkUp",
      "spokenSentence", "undoDown", "writeIt", "showListener",
      "repeat", "helperIcon", "helperForm", "writeCancel",
      "talkRecord", "newConversation", "learned", "health", "guideButton",
    ],
    moments: [
      { id: "talkCheck", ready: "check-down", steps: ["checkGuess", "checkDown", "checkUp", "writeIt"] },
      { id: "talkUndo", ready: "undo-down", steps: ["spokenSentence", "undoDown", "writeIt"] },
      { id: "talkSpoken", ready: "show-listener", steps: ["spokenSentence", "showListener"] },
      { id: "talkRepeat", ready: "repeat", steps: ["repeat"] },
      { id: "talkHelper", ready: "helper-icon", steps: ["helperIcon"] },
      { id: "talkWrite", ready: "helper-form", steps: ["helperForm", "writeCancel"] },
    ],
  },
  enroll: {
    ready: "enroll-progress",
    steps: [
      "enrollProgress", "enrollLanguage", "enrollStart",
      "enrollPhrase", "enrollSkip", "enrollRecord", "enrollRedo", "enrollListen", "enrollSave",
      "enrollFinished", "guideButton",
    ],
    moments: [
      { id: "enrollPhrase", ready: "enroll-phrase", steps: ["enrollPhrase", "enrollSkip", "enrollRecord"] },
      { id: "enrollReview", ready: "enroll-save", steps: ["enrollRedo", "enrollListen", "enrollSave"] },
      { id: "enrollFinished", ready: "enroll-finished-actions", steps: ["enrollFinished"] },
    ],
  },
  words: {
    ready: "words-tabs",
    steps: ["wordsTabs", "wordsAdd", "wordsRecord", "wordsDelete", "guideButton"],
    moments: [{ id: "wordsItem", ready: "words-record", steps: ["wordsRecord", "wordsDelete"] }],
  },
  settings: {
    ready: "settings-language",
    steps: ["settingsLanguage", "settingsTheme", "settingsVoice", "settingsPrivacy", "guideButton"],
    moments: [],
  },
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

/** Has this tour (a page id or a moment id) been shown, finished or closed, before? */
export const tourSeen = (id: string) => read(SEEN_PREFIX + id);
export const markTourSeen = (id: string) => write(SEEN_PREFIX + id);
/** The welcome card is shown once, before the very first tour. */
export const welcomed = () => read(WELCOMED_KEY);
export const markWelcomed = () => write(WELCOMED_KEY);

/** True while a guide bubble is open: timers on the page (the 5-second undo ring) wait. */
export const guideOpen = () => typeof document !== "undefined" && document.documentElement.dataset.guide === "open";
export function setGuideOpen(open: boolean): void {
  if (open) document.documentElement.dataset.guide = "open";
  else delete document.documentElement.dataset.guide;
}

export function findTarget(target: string): HTMLElement | null {
  const el = document.querySelector<HTMLElement>(`[data-guide="${target}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 ? el : null;
}

/** The steps whose element is on screen right now. */
export const visibleSteps = (ids: StepId[]): GuideStep[] =>
  ids.map((id) => STEPS[id]).filter((s) => findTarget(s.target) !== null);
