# Echo

Echo is an agentic AI that learns how one person with cerebral palsy (CP) or dysarthria speaks, then translates their speech into clear words for the people around them. Turkish and English first. Built for Capital Hacks.

## Folder layout

```
frontend/   Next.js + TypeScript + Tailwind (PWA): the phone/laptop app
backend/    FastAPI app: app/main.py, app/routes/, app/services/, app/agent/
phrases/    Enrollment phrase lists (tr.json, en.json)
uploads/    Audio recordings (git-ignored)
docs/       Project brief and build tasks
```

## Docs

- [Project brief](docs/Echo-Project-Brief.md): the problem, the solution and how the agent works.
- [Build tasks](docs/Echo-Build-Tasks.md): the step-by-step build plan.

## Run the backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env          # then fill in every key
python -m scripts.check_db    # optional: test only the MongoDB connection
uvicorn app.main:app --reload
```

Then open http://localhost:8000/health. It should return `{"status": "ok", "db": "connected"}`.
If a key is missing, the server refuses to start and lists exactly which keys to add.

Run the tests: `python -m pytest`

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000.

## Check how well Echo hears

```bash
cd backend
powershell -ExecutionPolicy Bypass -File scripts/make_test_audio.ps1   # clear test recordings (Windows voices)
python -m scripts.eval_asr tests/audio --enroll-dir tests/audio --limit 10
```

`eval_asr` runs each labelled recording through Whisper candidates and sound matching and prints a results table
(best guess, word error rate, whether sound matching found the right sentence, time per file).
Point it at real recordings by putting audio files and a `labels.json` (`{"file.webm": {"text": "...", "language": "tr"}}`) in a folder.

## Demo account

```bash
cd backend
python -m scripts.seed_demo                      # recordings generated with an ElevenLabs voice
python -m scripts.seed_demo --audio-dir my_recs  # or real recordings named {lang}-{phrase_id}.wav
```

Loads "Deniz" (Turkish + English) with recordings for every phrase, names and places, 31 approved
sentences (5 corrected by a helper) and a style profile. Running it again replaces the old demo account.
Open `/demo`, or tap "Try the demo account" on the welcome screen.

## Deploy on Render

`render.yaml` describes both services (Render > New > Blueprint). If you create them by hand instead:

| | API (`echo-api`) | Website (`echo-web`) |
|---|---|---|
| Runtime | **Python** (not Node: `backend/` has no package.json) | Node |
| Root directory | `backend` | `frontend` |
| Build command | `pip install -r requirements.txt` | `npm ci && npm run build` |
| Start command | `python -m app` (0.0.0.0, port `$PORT`) | `npm start` (0.0.0.0, port `$PORT`) |
| Environment | `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `MONGODB_URI`, `ELEVENLABS_API_KEY`, `PYTHON_VERSION=3.14`, `FRONTEND_URL=https://<website>.onrender.com` | `NEXT_PUBLIC_API_URL=https://<api>.onrender.com` |

- MongoDB Atlas > Network Access must allow `0.0.0.0/0`: Render has no fixed IP address.
- Region: **Oregon** for both services. The Atlas cluster runs in AWS us-west-2 (Oregon), so every database call stays local.
- Deploys come from `main` (auto-deploy on every push).
- The website build stops with a clear error if `NEXT_PUBLIC_API_URL` is missing; the API logs a warning if `FRONTEND_URL` is missing.
- Phones need HTTPS for the microphone. Render gives every service an `https://….onrender.com` address.
- Free services sleep after ~15 minutes idle; the first request then takes ~1 minute. Open the API's `/health` before a demo.
- `FRONTEND_URL` is the CORS allow-list (comma-separated for several sites).
- `NEXT_PUBLIC_API_URL` is baked in at build time: redeploy the website after changing it.
- ffmpeg comes from the `imageio-ffmpeg` package, so nothing extra needs installing.
- Render's free disk is wiped on every deploy, so saved recordings in `uploads/` don't survive a redeploy.
