---
name: agent-browser
description: Visual QA and iterative UI polish workflow for TradingBrowser. Use when validating layout, responsiveness, and regressions by capturing screenshots of local pages and comparing before/after changes.
---

# Agent Browser (TradingBrowser)

Use this skill to do quick visual iteration loops:
1. Start app
2. Capture screenshots for key pages
3. Apply UI fixes
4. Re-capture and compare

## Pages to verify
- `http://localhost:3000/dashboard`
- `http://localhost:3000/workspace`
- `http://localhost:3000/paper-console`
- `http://localhost:3000/swarm`
- `http://localhost:3000/settings`

## Setup
From repo root:

```bash
docker compose up -d --build frontend backend
```

Install playwright once in frontend (if missing):

```bash
cd frontend
npm i -D playwright
npx playwright install chromium
```

## Capture baseline/current screenshots

```bash
node .pi/skills/agent-browser/scripts/capture.mjs current
```

This writes images to:
- `.pi/skills/agent-browser/screenshots/current/`

## Create a baseline (first good state)

```bash
node .pi/skills/agent-browser/scripts/capture.mjs baseline
```

## Iteration rule
After each UI change:
1. Run `capture.mjs current`
2. Compare `baseline` vs `current`
3. Fix spacing/readability/usability regressions
4. Repeat

## QoL checklist
- Primary actions visible above fold
- Important status visible without scrolling (mode, health, live/stub)
- Mobile menu usable with one tap
- No overflowing text blocks
- Consistent card spacing and typographic scale
- Errors visible and actionable
