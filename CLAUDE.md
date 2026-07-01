# CLAUDE.md - MenuCaptain Frontend

Auto-read by Claude Code at session start. Keep it current.

**Doc currency (see starter spec §5):** keep this file + the architecture doc in step
with the code in the SAME session you change code. Don't hardcode the version here
(point to `APP_VERSION` + `/health`); update the doc body when the architecture changes;
log dated changes in the app's Log folder. Rule: `CG Apps\Forever Apps\forever-apps-starter-spec.md`.

## What this is
MenuCaptain frontend: a SINGLE-FILE HTML PWA (React via CDN + Babel
standalone), hosted on GitHub Pages at the custom domain menucaptain.com.
Part of MenuCaptain - a solo-dev consumer SaaS. The backend is a SEPARATE
repo (`dining-captain-backend`, FastAPI on Railway).

## Coordinates
- Repo: `cgramlich/dining-log-app` (public). GitHub username is `cgramlich`
  - NO "j" (easy to mistype as the email handle cjgramlich).
- Live URL: https://menucaptain.com (GitHub Pages via CNAME).
- Deploy: push to `main` -> GitHub Pages redeploys.
- The ENTIRE app is one file: `index.html` (~597 KB). Deliverable file name
  is exactly `index.html`.
- Version: the source of truth is the `APP_VERSION` constant in `index.html` (the
  in-app self-update banner reads it live). Do NOT hardcode the current number in
  this doc — it drifts. Bump on EVERY deploy (so installed users update), following
  semver: **patch** (third number) for tweaks/fixes — this is MOST changes;
  **minor** (middle) only for a notable user-facing feature; **major** for a
  redesign or breaking change. Keep `sw.js` VERSION in lockstep. Never decrease it
  (`isNewer` needs strictly-greater, so a lower number would stop everyone updating).
- Backend base URL: `API_BASE_DEFAULT` in `index.html` (~line 840) =
  https://web-production-cbd3b.up.railway.app
- Sharing: lists/menus publish a static page to the Pages repo (`/l/`,`/m/`).
  VISITS are different - `shareVisit()` posts to the backend, which serves the
  preview page INSTANTLY at `SHARE_BASE_URL/v/<slug>` (no Pages build delay);
  it bounces to the app's `?visit=` viewer. Falls back to the long `?visit=`
  link if the backend is unreachable. (Moving lists/menus here too is a TODO.)

## PWA self-update mechanism (why version bumps matter)
Installed PWAs cache hard. On load + on a manual "check for updates", the
app refetches `index.html` with `cache:"no-store"`, regexes out
`APP_VERSION`, compares, and shows an "update available" banner if newer.
So bump `APP_VERSION` on EVERY deploy or installed users silently never update.
MAJOR.MINOR.PATCH — default to a PATCH bump (fixes/tweaks); reserve MINOR for a
real feature and MAJOR for a redesign. `isNewer` compares all three numbers, so
a patch bump does trigger the banner. Bump `sw.js` VERSION to match.

## How Chris works
- Plain-English feedback. He describes changes conversationally; you read
  the code and make the edits directly. Iterate ("no, smaller") freely.
- Ask before building. Feature work gets a SHORT design proposal and
  sign-off before code. One step at a time; wait for confirmation.
- Debug logs-first: ask for the browser console output / network response
  / a screenshot before theorizing. Do not guess.
- Direct communication, no hedging. Honest engineering answers.
- Production-ready, not demos.
- Any commands you hand to Chris: ONE per code block, never grouped, wait
  for output. Copyable content always inside a code block.
- Environment: Windows 11, Command Prompt. Keep any console/log output
  ASCII-safe (no emoji) - CMD cannot render Unicode.

## Verify before delivering
- Single-file React via Babel standalone: run the JSX through Babel
  standalone in Node to confirm it transforms cleanly BEFORE delivering.
  Then content-grep to confirm each intended change is present.
- For automated edits, assert each anchor string appears EXACTLY ONCE
  before replacing. Watch for substring collisions: a more-deeply-indented
  duplicate of a line CONTAINS the shallower copy as a substring, so anchor
  with a leading newline or extra surrounding context.
- One change set per deploy (tiny low-risk fixes may ride along; never a
  second feature).

## Frontend/UI gotchas (see playbook sections 1, 7, 8 for the full list)
- Host big binary assets (wheel image, backdrop) by URL as repo files -
  NEVER inline them as base64 in index.html (keeps the file lean and the
  version-check fetch cheap). Verify each asset URL loads and the extension
  matches EXACTLY (a `.jpeg` vs `.jpg` mismatch 404s silently).
- Two full-screen overlays cannot share one overlay variable - nest the
  second as a higher-z layer and hand its result back via callback, so the
  host keeps its draft.
- `.btn` base is `width:100%`. A button in a flex row next to text needs a
  `width:auto` variant (e.g. `.btn.sm`) or it crushes the text. Base CSS
  defined AFTER component CSS can override it - inline style may be needed
  to win.
- Stop tap-bubbling on controls inside a tappable card, or the inner tap
  also fires the card handler.

## Git note
Plain `git` works normally here - you are on the real filesystem. The
"sandbox phantom-diff, don't trust sandbox git" warning in the handoff is a
Cowork-sandbox-only issue and does NOT apply to Claude Code.
`core.autocrlf=input` is set globally.

## Reference docs (read for full context; keep in sync)
- Architecture & ops playbook:
  `C:\Users\cjgra\Dropbox\My AI\CG Apps\MenuCaptain\MenuCaptain Architecture & Design\app-architecture-playbook.md`
- Dev-loop handoff:
  `C:\Users\cjgra\Dropbox\My AI\CG Apps\MenuCaptain\MenuCaptain Architecture & Design\cowork-dev-loop-handoff-2026-06-18.md`
