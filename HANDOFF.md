# MenuCaptain — HANDOFF

**True as of 2026-08-28.** Read this before changing anything. It says what is true *now* and
why — not what happened (git has that). Companion: `BRIEFING.md` (deck-ready, leaves the
machine). When the two disagree, **this file is right**.

---

## What this is

A private notebook for eating out. You scan or link a restaurant menu, log what you ate with
photos and a rating, split the check, run a group order or a "where shall we eat?" vote, and
keep a searchable history of every visit. It is a personal-memory product first and a
coordination product second — the group features exist because eating out is rarely solitary,
not because it is a social network. There is no feed and no public profile.

Live at **menucaptain.com**. Installable as a PWA; a Capacitor shell exists for the app stores.

---

## Current state — 2026-08-28

| Piece | Version | Where |
|---|---|---|
| Web app | **1.430.0** | menucaptain.com (GitHub Pages), confirmed live |
| Backend | **0.119.0** | Railway, `/health` reports `db connected` |
| Native shell | **1.430.0** | built and pushed, **not yet submitted to any store** |

All three repos are clean and level with `origin/main`. Backend `/health` reports ai, places,
stripe and Serper all configured.

**One branch is parked deliberately:** `hold/price-3.99` in `dining-log-app` holds the Pro price
display change ($3.99/mo, $29.99/yr). It is **not** merged. Merge it only when Chris has set the
matching Stripe prices — merging early puts a price on screen that Stripe will not charge.

---

## The map

Three repos, all under `C:\Users\cjgra\`, all pushed to GitHub under `cgramlich`.

| Repo | Owns |
|---|---|
| `dining-log-app` | The whole front end. **One file**: `index.html`, ~1.38 MB, React via CDN + Babel standalone. Plus `sw.js` (service worker) and `manifest.json`. |
| `dining-captain-backend` | FastAPI `main.py` (~7,500 lines) + `sql/*.sql` migrations. Supabase for data and photo storage. |
| `menucaptain-native-build` | Capacitor shell. `build.js` precompiles the JSX out of `index.html`, vendors the CDN deps, and stamps the Android version. |

**`index.html` is genuinely one file and that is on purpose** — no build step for the web app,
so a deploy is a git push. Do not "modernise" this into a bundler without asking; it is the
reason the deploy story is as simple as it is.

`verify_compile.js` in the native repo compiles `index.html` and reports the byte count. Run it
after **every** front-end edit — it is the only syntax check the web app has.

---

## How to run, build and deploy

Check the front end still compiles (do this after every edit):

```bash
cd /c/Users/cjgra/menucaptain-native-build && node verify_compile.js
```

Deploy the web app — bump `APP_VERSION` in `index.html` **and** `VERSION` in `sw.js` to the same
new value first, then:

```bash
git -C /c/Users/cjgra/dining-log-app push origin main
```

Confirm it actually went out (GitHub Pages takes ~1 minute):

```bash
curl -s "https://menucaptain.com/?vcheck=$(date +%s)" | grep -ao 'APP_VERSION *= *"[0-9.]*"'
```

Deploy the backend — Railway redeploys on push:

```bash
git -C /c/Users/cjgra/dining-captain-backend push origin main
```

Confirm the backend is live on the version you pushed:

```bash
curl -s https://web-production-cbd3b.up.railway.app/health
```

Rebuild the native bundle after a front-end change:

```bash
cd /c/Users/cjgra/menucaptain-native-build && node build.js
```

Gradle needs an explicit JDK on this machine:

```bash
JAVA_HOME="C:\Program Files\Android\Android Studio\jbr" ./gradlew assembleDebug
```

---

## Decisions, dated, with the road not taken

**This is the section that stops a future session "fixing" something deliberate.**

### Guest identity — never infer a link (2026-08-19 → 20)

A group order identifies a guest by `guest_token`, a **device**, with a free-text name beside it.
Linking that to a person is a whole subsystem, and every part of it refuses to guess.

- **`guest_identities.source` has exactly two legal values, `confirmed` and `account`.** There is
  deliberately no `inferred`, and the CHECK constraint enforces it. The database itself refuses a
  link that no human and no authenticated session stands behind.
- **Keyed on the device token, not the name.** A token is stable across orders, so one
  confirmation covers every future order from that phone. Names are the unreliable half — the
  same person types "Mark", "Mark H", "mark".
- **Rejected: auto-merging on a matching name.** Two Marks at one table is ordinary, and a wrong
  merge writes bad history that produces *no error* — suggestions just quietly describe the wrong
  person. Confirmed links only.
- **A changed name re-opens the question.** If a submission arrives under a name that differs
  from the `seen_as` on an existing link, the backend flags it rather than filing it. That is the
  shared-phone case: somebody handing their phone over to add their own order.
- **A memory-only token is refused outright** (`stable: false` → 400). It dies with the tab, so
  the link would point at something that can never return.

### `likelySamePerson` is narrow on purpose (2026-08-23)

Fires only on word-boundary containment — a lone first name matching the other's first name, or
same first name plus same next initial. It correctly refuses "Baker" vs "Trent Baker" (surname)
and "Baker" vs "Bakery Jones".

**Do not widen it.** Its answer gets acted on — it offers a merge the host taps — so a loose net
produces confident nonsense. If it feels too strict, that is the design. Ten cases are pinned in
the commit message for 1.422.0.

### Order suggestions — privacy is the query, not a note (2026-08-22)

`GET /api/guest/history` searches **only group orders the caller hosted**. You learn what someone
ordered when they ate with you, which you were present for. Their history with anyone else is not
reachable from any endpoint. This is enforced in the query, not in a comment, so it cannot drift.

Name matching **is** allowed on this read path and still refused on the write path. The read
shows the host a suggestion beside the name it came from, and they can judge it; a permanent
merge on the same evidence would be invisible and unfixable.

### `myUsualAt` needs a repeat and two visits (2026-08-19)

"You usually get" counts a dish **once per visit** — ordering two for the table is not a stronger
habit than coming back for it twice — and shows nothing at all until there are two visits and a
repeat. One visit is a record, not a habit. Returning `[]` is correct behaviour, not a bug.

### Dead vote codes live in `localStorage` (2026-08-25)

Three earlier attempts cleared the vote code from the address bar and then from `sessionStorage`.
**Both were overwritten on the next launch**, because the code does not come from the page: iOS
restarts a standalone PWA at its *saved launch URL*, which still carries `?v=`. `replaceState`
rewrites the current history entry and cannot touch what the OS hands the app next time.

So the app stops removing the code and remembers the **answer** instead — a capped list of dead
codes in `localStorage`, which outlives a relaunch. The router ignores those codes however they
arrive. A 404 is safe to treat as final: nothing purges votes, and closed ones still load with
their tally.

### Share links open in-app for people who have an account (2026-08-19 → 25)

The router used to check share parameters *before* checking for a session, so a signed-in person
tapping their own shared visit got the public no-account viewer. Now a device with an account
lands in the real app with the content as an overlay. Everyone else still gets the public viewer
— that is what a share link is *for*, and it must keep working with no account.

The signed-in test is **synchronous** (`configComplete(loadConfig())`, the same question
`PublishedVisit` asks for its Save button), so there is no await and no flash of the wrong screen.

Vote codes are additionally held in `sessionStorage` so a refresh keeps your place in a *live*
vote — that store has no say in what the app loads, so it cannot park anything.

### Notes and "About this place" are two fields (2026-08-19)

Split because they are read at different moments — hours before you set off, the story while
you are sitting there. **And because the Google enrich writes to `notes`** (`"Hours: ..."`), so
anything interesting typed there was liable to be overwritten. Do not merge them back.

### Money is one section; Receipts is inside it (2026-08-19)

Receipts was briefly its own section and that was wrong. A receipt is the evidence for the money,
not a second topic. Split, expense and receipts are one job: settle up, keep the proof, get paid
back.

### A scanned total is an override, and the app says so (2026-08-19)

Scanning a receipt sets the total, which puts the split form in override mode before you touch
anything — so editing tax or tip moves nothing on screen. Rather than silently recalculating
(service charges, comps and corkage are on the bill but not in the items, so the scanned figure
is often *right*), the app shows the disagreement and offers the computed figure as one labelled
tap. **Do not make this auto-correct.**

### Models and pricing (2026-08, standing)

All six AI tasks run on **`claude-sonnet-5`**. `AI_PRICES` in `main.py` **is the allow-list** —
a model missing from that dict 400s every call that uses it. Adding a model means adding its
price in the same edit. Sonnet is the floor; there are no Haiku routes.

### RLS: enabled, no policies (standing)

Every public table has RLS **on** with **no policies** — only the backend's service role reads or
writes. "Run without RLS" is a critical exposure via the public anon key. Every new table also
needs an explicit `grant all ... to service_role`.

---

## Traps — each one has already cost time

**A new Supabase table 500s with `42501` until it is granted.** Even with default privileges in
place. Every `sql/*.sql` file carries an explicit `grant all on <table> to service_role;` for
this reason. `group_vote.sql` shipped without it once and the ballots endpoint failed in
production.

**Bash heredocs mangle backslash escapes.** A JS regex like `/\s+/` written inside an unquoted
heredoc arrives corrupted. This happened four times in one week. Write patch scripts to a `.py`
file and run the file, or use the Write tool. Always re-read what landed in `index.html`.

**Duplicate top-level function names silently override.** `cityFromAddress` already exists at
`index.html:1268` with six callers. A second definition added later in the file *wins*, silently,
across all of them. Before adding a helper, grep for the name.

**Build the native bundle from the pushed commit, not the working tree.** A bundle was once built
while `hold/price-3.99` was in the tree and shipped a price that was not live. `build.js` reports
the version and byte count — check they match `verify_compile.js`.

**`APP_VERSION` and `sw.js` `VERSION` must move together, every deploy.** If they do not,
installed users silently never update. This is the single most common way a fix appears not to
work.

**iOS resumes a standalone PWA at its saved launch URL.** Not `start_url` — the manifest is
correct and irrelevant here. Anything the app puts in the address bar can come back on the next
launch, and `replaceState` cannot prevent it. Design for "this URL will be handed to me again".

**`fetch` has no timeout of its own.** Photo upload hung indefinitely on a weak connection until
an `AbortController` was added (60s per photo). Any new network call that a user waits on needs
the same treatment.

---

## What is open

**Blocked on Chris — nobody else can do these:**
- iOS build machine (leaning MacBook Air 512GB), then TestFlight
- Google Play Console registration and the Android release keystore
- Store listing details: subtitle, Google title, age rating, demo account
- Stripe prices, then `git merge hold/price-3.99`

**Known bugs, unfixed and deliberate about it:**
- `?g=` group-order links can park the installed app exactly like `?v=` used to. The same fix
  applies; it was left because the right in-app destination for a group order is a product
  decision, not a mechanical copy of the vote one.
- Menu and list share links still route to the public viewer for signed-in users. Only *visit*
  shares were fixed.

**Parked, with reasoning:**
- On Edit visit, "Add a name `[Add]`" sits directly above "Search or type a dish `[Add]`" — two
  identical-looking rows. This produced a real bug (a person saved as a dish). 1.430.0 *detects*
  the collision and offers to fix it, but the underlying adjacency is untouched. The real fix is
  making the two rows visibly different jobs.
- Group order → logged visit, and a retention policy for group-order data. Both proposed, neither
  approved.

---

## Where authority lives

| Question | Truth |
|---|---|
| Is it deployed, and on what version? | `/health` for the backend; `?vcheck=` for the app. Never a doc. |
| What the code does and why | The comments beside it — see `CODE-READABILITY-STANDARD.md` |
| What is true about the project now | **This file** |
| Numbers quoted to an outside audience | `BRIEFING.md`, which derives from this file |
| Secrets and keys | Railway env and vendor dashboards **only**. Never in chat, never in git. |

**This project has a single writer.** One session edits these three repos. Findings from other
sessions get routed here rather than applied directly, so that changes are made by someone
holding the context in this file.
