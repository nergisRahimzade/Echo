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
