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
