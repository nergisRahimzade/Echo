# Echo — Build Tasks

Nov 6, 2026 · @Nergis

Echo is built in 7 phases of small tasks; phases 0-5 are the MVP, phase 6 is polish and demo, the last section is stretch work. Read together with **Echo — Project Brief** (`Echo-Project-Brief.md`).

## How to use this doc with Claude Code

- Give Claude Code both docs. Do **one task per prompt**, in order; each task is small enough to finish and test in one go.
- Every task has: **Plain words** (what we are doing), **Technical** (how), **Done when** (how to check).
- After each task, Claude Code explains in simple terms what each new or changed file does, then commits with a message like `task 2.3: whisper candidates`.

**Folder layout:**

```
echo/
  frontend/   Next.js + TypeScript + Tailwind (PWA)
  backend/    FastAPI app: app/main.py, app/routes/, app/services/, app/agent/
  phrases/    tr.json, en.json
  uploads/    audio files (git-ignored)
  docs/       these two docs as Markdown
```

**API contract (backend):**

| Method | Path | In | Out |
| --- | --- | --- | --- |
| POST | `/users` | name, main_language | user_id |
| GET | `/phrases?lang=tr` | language | list of enrollment phrases |
| POST | `/enroll` | user_id, phrase_text, audio | sample_id |
| POST | `/words` | user_id, list of names/places | ok |
| POST | `/translate` | user_id, session_id, audio | utterance_id, sentence, score, action (`speak` or `check`), language |
| POST | `/feedback` | utterance_id, verdict (`up` or `down`), final_text (helper fix only) | ok, next_action |
| POST | `/tts` | text, language | audio (mp3) |
| DELETE | `/users/{id}/data` | user_id | ok |

**MongoDB collections:** `users`, `enrollment_samples`, `personal_words`, `utterances`, `style_profiles`.

## Phase 0 — Project setup

- [ ] **0.1 Create the folders and git repo**
  - Plain words: make the empty project boxes.
  - Technical: create the folder layout above, a root `README.md`, `.gitignore` (node_modules, .venv, uploads/, .env).
  - Done when: `git status` is clean after the first commit.
- [ ] **0.2 Start the backend**
  - Plain words: a tiny server that answers "I'm alive".
  - Technical: FastAPI app in `backend/app/main.py`, `GET /health` returns `{status: "ok"}`, CORS open to the frontend URL, `requirements.txt`.
  - Done when: `uvicorn app.main:app --reload` runs and `/health` returns ok.
- [ ] **0.3 Start the frontend**
  - Plain words: an empty app screen with one big button.
  - Technical: Next.js (App Router, TypeScript, Tailwind) in `frontend/`; home page with a large "Hold to talk" button (at least 120 px tall) and a header.
  - Done when: `npm run dev` shows the page on phone and laptop.
- [ ] **0.4 Connect the database**
  - Plain words: give the server a notebook to remember things.
  - Technical: MongoDB Atlas cluster, `backend/app/db.py` with Motor (async driver), create the 5 collections, indexes on `user_id`.
  - Done when: `/health` also reports `db: connected`.
- [ ] **0.5 Secret keys file**
  - Plain words: one safe place for passwords to outside services.
  - Technical: `backend/.env.example` with every key from the brief; load with `pydantic-settings` in `app/config.py`.
  - Done when: the app fails with a clear message if a key is missing.
- [ ] **0.6 Frontend talks to backend**
  - Plain words: the app can call the server.
  - Technical: `frontend/lib/api.ts` with typed functions for every endpoint in the API contract (stubs are fine); `NEXT_PUBLIC_API_URL` env var.
  - Done when: the home page shows the backend health status.

## Phase 1 — Enrollment (teach Echo your voice)

- [ ] **1.1 Write the phrase lists**
  - Plain words: 20 everyday sentences per language for the user to repeat after hearing them.
  - Technical: `phrases/tr.json` and `phrases/en.json`, each item `{id, text, category, icon}` (greetings, needs, feelings, questions, yes/no). Mix short and long sentences. `GET /phrases?lang=` returns them.
  - Done when: both files load and the endpoint returns 20 items each.
- [ ] **1.2 Create a user**
  - Plain words: sign up with a name and main language.
  - Technical: `POST /users` saves `{name, main_language, threshold: 0.80, created_at, consent: true}`; frontend onboarding screen with a consent checkbox (a helper can complete it); store `user_id` in localStorage.
  - Done when: refreshing the page keeps the same user.
- [ ] **1.3 Build the recorder**
  - Plain words: hold the button to record, let go to stop.
  - Technical: `frontend/components/HoldToRecord.tsx` using MediaRecorder (webm/opus); press-and-hold and also tap-to-start/tap-to-stop mode (for users who can't hold); shows a timer and a level meter.
  - Done when: a recording plays back in the browser.
- [ ] **1.4 Save enrollment recordings**
  - Plain words: each recording is saved with the sentence it was meant to be.
  - Technical: `POST /enroll` (multipart) saves audio to `uploads/{user_id}/{sample_id}.webm` and a doc `{user_id, phrase_id, text, language, audio_path}` in `enrollment_samples`.
  - Done when: 3 test recordings appear in the folder and the database.
- [ ] **1.5 Enrollment screen**
  - Plain words: Echo says one sentence aloud, the user repeats it, then moves on. No reading needed.
  - Technical: `/enroll` page: plays each phrase with TTS (big replay icon), shows a simple picture per phrase, recorder, redo and next as icons, progress ring; user can skip a phrase.
  - Done when: a full 20-phrase run saves 20 samples.
- [ ] **1.6 Personal words**
  - Plain words: the user (or a helper) types names of family, friends, places, pets.
  - Technical: `POST /words` saves to `personal_words`; simple form with chips; optional: record each name once (saved as an enrollment sample).
  - Done when: words are saved and listed back.

## Phase 2 — Speech recognition (hear the words)

- [ ] **2.1 Clean up the audio**
  - Plain words: turn every recording into the same simple format.
  - Technical: `services/audio.py` converts webm to 16 kHz mono WAV with ffmpeg; trims long silence at start and end.
  - Done when: any uploaded file becomes a playable WAV.
- [ ] **2.2 Transcribe with Whisper**
  - Plain words: get a first guess of the words.
  - Technical: `services/asr.py` with `transcribe(wav, language, prompt)`; calls the hosted Whisper API; `prompt` = the user's personal words + 10 most-used approved phrases; returns text + detected language.
  - Done when: a clear test sentence in Turkish and in English is transcribed correctly.
- [ ] **2.3 Get several guesses**
  - Plain words: ask for 2-3 different guesses, not just one.
  - Technical: `get_candidates()` runs Whisper with and without the personal prompt (and once with temperature 0.4), removes duplicates, returns a list.
  - Done when: one recording returns 2-3 candidate strings.
- [ ] **2.4 Fingerprint enrollment recordings**
  - Plain words: turn each saved recording into numbers that describe how it sounds.
  - Technical: `services/voiceprint.py` computes an audio embedding (Whisper encoder output, mean-pooled, or a speech embedding model); store the vector on each `enrollment_samples` doc when it is saved.
  - Done when: every sample has an `audio_vector` field.
- [ ] **2.5 Sound matching**
  - Plain words: compare a new recording to the user's past recordings and find the closest ones.
  - Technical: `match_sound(wav, user_id)` embeds the new audio, cosine similarity against the user's sample vectors (and approved utterances later), returns top 3 `{text, score}`.
  - Done when: re-saying an enrolled phrase returns that phrase as the top match.
- [ ] **2.6 Test script**
  - Plain words: a quick way to check how good the hearing is.
  - Technical: `backend/scripts/eval_asr.py` runs a folder of labelled recordings through candidates + matching and prints accuracy and time per file.
  - Done when: the script prints a results table.

## Phase 3 — The agent (understand what they meant)

- [ ] **3.1 Agent rules (system prompt)**
  - Plain words: write the agent's job description.
  - Technical: `agent/prompt.py`: "You translate the speech of a person with dysarthria. Translate, never invent or add meaning. Keep their words and style. Reply in the language they spoke. Always return exactly ONE sentence." Output must be JSON `{sentence, confidence 0-1, language, reason}`. No options list.
  - Done when: the prompt is in its own file with 3 worked examples (Turkish and English).
- [ ] **3.2 Memory tools**
  - Plain words: give the agent ways to look things up about the user.
  - Technical: `agent/tools.py` with `search_similar_sentences(text)` (Atlas Vector Search over approved utterances), `get_personal_words()`, `get_style_profile()`, `get_recent_turns(session_id, n=5)`. Each returns short JSON.
  - Done when: each tool works on its own in a test.
- [ ] **3.3 Agent loop**
  - Plain words: the agent reads the guesses, looks things up, and decides on one sentence.
  - Technical: `agent/run.py` calls Claude with tool use: input = Whisper candidates + sound-match results + language; loop until it returns the final JSON; max 3 tool rounds; validate JSON with Pydantic.
  - Done when: given fake candidates, it returns valid JSON with one sentence every time.
- [ ] **3.4 Combined score**
  - Plain words: decide how sure Echo really is, not just how sure the AI says it is.
  - Technical: `services/scoring.py`: `score = 0.5 * agent_confidence + 0.25 * candidate_agreement + 0.25 * sound_match_similarity`, all 0-1. Agreement = average text similarity (e.g. normalized edit distance) between Whisper candidates and the final sentence. Keep the weights in `config.py`.
  - Done when: unit tests show identical candidates + strong sound match score above 0.80, and messy ones below.
- [ ] **3.5 The translate endpoint**
  - Plain words: one call that goes from audio to one clear sentence and a decision.
  - Technical: `POST /translate` = audio clean-up → candidates → sound match → agent → score; `action = "speak"` if score is at least the user's threshold (default 0.80), else `"check"`; saves the utterance (status `pending`, attempt number) and returns it.
  - Done when: a recording sent from Postman returns one sentence, a score and an action.
- [ ] **3.6 Conversation memory**
  - Plain words: remember the last few things said, so the agent understands the topic.
  - Technical: frontend makes a `session_id` per conversation; a helper can optionally type what the other person said, stored as a turn.
  - Done when: the agent's reason mentions earlier turns when relevant.
- [ ] **3.7 Speed check**
  - Plain words: make sure it's fast enough to talk.
  - Technical: log time per step; run Whisper calls in parallel with `asyncio.gather`; target under 4 seconds end to end.
  - Done when: timings print in the server log and average under 4 s.

## Phase 4 — Confirm and speak

- [ ] **4.1 Conversation screen**
  - Plain words: the main screen the user talks through.
  - Technical: `/talk` page: big hold-to-talk button, a "thinking" animation (no text), then the result; icons only for the user, large text only for the listener.
  - Done when: speaking gives a result within a few seconds.
- [ ] **4.2 Speak when sure (score 0.80 or higher)**
  - Plain words: if Echo is sure, it just says it.
  - Technical: on `action = "speak"`, play `/tts` audio aloud and show the sentence in large text; keep a big thumbs-down icon on screen for 5 seconds; a tap sends `/feedback` with `down`.
  - Done when: a high-score result is spoken with no tap needed.
- [ ] **4.3 Check with the user (score below 0.80, no reading needed)**
  - Plain words: if Echo isn't sure, it whispers its guess to the user only and waits for a thumbs up or down.
  - Technical: on `action = "check"`, play the sentence at low volume (or to earphones) and show only three huge icons: thumbs up (green), thumbs down (red), replay (speaker). No text. Up → speak aloud + `/feedback up`. Down → play a recorded prompt "say it again" in the user's language, show a big repeat icon, `/feedback down`.
  - Done when: the whole check can be done by someone who cannot read.
- [ ] **4.4 Helper fallback**
  - Plain words: after two wrong guesses in a row, stop guessing and let a helper type it.
  - Technical: if `/feedback` returns `next_action = "helper"` (second `down` for the same message), show a "helper" icon that opens a text box for the listener or caregiver; saves as `final_text`.
  - Done when: two thumbs-downs open the helper screen.
- [ ] **4.5 Text-to-speech endpoint**
  - Plain words: turn the sentence into a clear voice.
  - Technical: `POST /tts` calls ElevenLabs with a Turkish or English voice by language, returns mp3; cache by text hash; fallback to the browser's `speechSynthesis`. Pre-record the "say it again" prompts in both languages.
  - Done when: Turkish and English sentences both play aloud.
- [ ] **4.6 Listener view**
  - Plain words: show the sentence so the other person can read it too.
  - Technical: a "show to listener" icon that fills the screen with the sentence (optionally flipped 180° for someone sitting opposite).
  - Done when: the full-screen view opens and closes with one tap.

## Phase 5 — Learning loop (get better every day)

- [ ] **5.1 Save feedback**
  - Plain words: remember whether each sentence was right.
  - Technical: `POST /feedback` updates the utterance: `verdict`, `final_text`, `was_corrected`, status `approved` or `rejected`; a sentence spoken at 0.80+ with no thumbs-down within 5 s counts as approved.
  - Done when: approved and rejected utterances show in the database with their audio path.
- [ ] **5.2 Add approved sentences to memory**
  - Plain words: each approved sentence becomes a new example the agent and sound matcher can use.
  - Technical: on approval, compute a text embedding (for Atlas Vector Search) and an audio vector (for sound matching) and store both on the utterance. Rejected guesses are kept as "not this" examples the agent can see.
  - Done when: saying the same sentence a second time matches the first one with a higher score.
- [ ] **5.3 Learn from helper fixes**
  - Plain words: when a helper types the right sentence, link it to the user's recording.
  - Technical: save the helper's `final_text` + the audio as an approved, corrected utterance with extra weight in sound matching.
  - Done when: the corrected sentence scores 0.80+ on the next try.
- [ ] **5.4 Style profile**
  - Plain words: learn how the user likes to talk.
  - Technical: every 10 approvals, a background job sends the latest approved sentences to Claude and saves a short `style_profiles` doc: favourite words, typical sentence length, formality, humour, common phrases. The agent reads it via `get_style_profile()`.
  - Done when: the profile updates after 10 approvals.
- [ ] **5.5 Smarter hints for Whisper**
  - Plain words: words the user often says become hints for the listener.
  - Technical: build the Whisper `prompt` from personal words + most frequent approved phrases; refresh on each approval.
  - Done when: a frequently used name stops being misheard.
- [ ] **5.6 Per-user threshold tuning**
  - Plain words: adjust how sure Echo must be, based on how often it was right for this user.
  - Technical: store `threshold` on the user (default 0.80). After 30 spoken sentences and then every 20: if more than 5% of auto-spoken sentences got thumbs-down, +0.05; if more than 90% of checks got thumbs-up, −0.05; clamp to 0.70-0.90. Log every change.
  - Done when: a simulated run of feedback moves the threshold as expected.
- [ ] **5.7 Show progress**
  - Plain words: let the user (and helpers) see it's learning.
  - Technical: a progress ring icon that fills as approved sentences grow, plus a number for helpers ("42 sentences learned").
  - Done when: the ring grows after each approval.

## Phase 6 — Turkish/English, polish and demo

- [ ] **6.1 Two-language interface**
  - Plain words: every button and message in Turkish and English.
  - Technical: `frontend/locales/tr.json` and `en.json` with a small `t()` helper; language switch in settings; default from the user's main language. Structure it so a new language = one new file.
  - Done when: switching language changes every visible text and every spoken prompt.
- [ ] **6.2 Mixed-language speech**
  - Plain words: handle users who switch between Turkish and English.
  - Technical: let Whisper auto-detect per utterance when the user picks "both"; the agent keeps the language mix the user used; TTS picks the voice by detected language.
  - Done when: a Turkish sentence and an English one in the same session both come out right.
- [ ] **6.3 Accessibility pass**
  - Plain words: make it easy to use with shaky hands, tired eyes, or without reading.
  - Technical: all touch targets at least 64 px, high contrast, no timeouts, tap-to-start mode as well as hold, icons + sounds for every user-facing action, works with screen zoom and switch access; check with Lighthouse accessibility.
  - Done when: Lighthouse accessibility score is 95 or higher.
- [ ] **6.4 Privacy controls**
  - Plain words: the user controls their voice data.
  - Technical: consent text on signup (also read aloud); `DELETE /users/{id}/data` removes all docs and audio files; "Delete my data" button in settings.
  - Done when: after deleting, nothing for that user is left in the database or `uploads/`.
- [ ] **6.5 Demo user**
  - Plain words: prepare a ready-trained account for the judges.
  - Technical: `scripts/seed_demo.py` loads a demo user with enrollment samples, personal words and ~30 approved sentences in both languages (recorded with a teammate imitating slurred speech, or from consented volunteers).
  - Done when: logging in as the demo user shows learned sentences.
- [ ] **6.6 Deploy**
  - Plain words: put it online so it works from a phone.
  - Technical: frontend on Vercel, backend on Render or Railway (needs ffmpeg in the image), MongoDB Atlas allowlist; HTTPS (needed for mic access).
  - Done when: the full flow works on a phone over the internet.
- [ ] **6.7 Demo script and backup**
  - Plain words: plan the 3-minute pitch and have a backup.
  - Technical: script: problem (30 s) → live demo of a Turkish and an English sentence, one below-0.80 check answered with a thumbs up, one correction that works on the next try (2 min) → vision and more languages (30 s). Record a backup video of the full flow.
  - Done when: the demo runs start to finish twice in a row.

## Stretch tasks (only after the MVP works)

- [ ] **S.1 The user's own voice** — with consent, create a custom ElevenLabs voice from the user's clearest recordings so the output sounds like them.
- [ ] **S.2 Caregiver view** — a second login where a family member or therapist adds names, phrases and corrections for the user.
- [ ] **S.3 Personal Whisper fine-tune** — once a user has 200+ approved sentences, train a LoRA adapter on their recordings and compare accuracy with `eval_asr.py`.
- [ ] **S.4 Quick phrases** — one-tap picture buttons for the 8 sentences the user says most, built from approved utterances.
- [ ] **S.5 Phone-call mode** — route the translated voice into a call or video meeting.
- [ ] **S.6 More languages** — add a phrase list, UI file and TTS voice for a third language to prove the language design works.