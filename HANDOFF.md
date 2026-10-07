# MenuCaptain — HANDOFF

**True as of 2026-09-16.** Read this before changing anything. It says what is true *now* and
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

## Current state — 2026-09-28

| Piece | Version | Where |
|---|---|---|
| Web app | **1.491.0** | menucaptain.com (GitHub Pages), confirmed live |
| Backend | **0.128.0** | Railway, `/health` reports `db connected` |
| Native shell | **1.491.0** | built and pushed, **not yet submitted to any store** |

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

Refresh the promo brief **after both deploys are confirmed live**. It records what is running,
so running it earlier stamps the old version (the page would say the new one is "on its way"):

```bash
cd "/c/Users/cjgra/Dropbox/My AI/CG Apps/MenuCaptain/MenuCaptain Promo" && python make_living_promo.py
```

Then republish `menucaptain-promo-living.html` to the promo artifact
(https://claude.ai/artifact/DXPkph4v7MmRyihNhqQqKX). If it prints `INVENTORY BEHIND`, draft
inventory lines in `living-promo-template.html` for the changes that need one, show them to Chris
(he corrects the wording), then bump `data-inventory-as-of`.

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

### The share funnel — what it measures and what it refuses to (2026-09-01)

The share card is the **only** surface in the app that reaches somebody without an account.
"Send to a friend" is not one: it delivers into "Shared with you" and needs an accepted
connection both ways, so both parties already have accounts by construction. Two share paths,
two jobs — do not conflate them.

**The fix that mattered was one line.** The signup button on a shared place page pointed at the
bare homepage, so the recommendation was discarded at the exact moment somebody converted; their
first screen was an empty app rather than the restaurant a friend sent them. It now stores the
page URL and returns them there after signup, with "Add to my places" live.

**Rejected: applying the place automatically after auth.** `doSave` lives inside
`PublishedMenu`, and extracting it would be real surgery in a 1.1 MB file for a marginal gain —
and nothing should be silently written into an account made ten seconds ago. A return plus one
tap gets the same outcome and leaves the choice with the user.

The return target is **one-shot and expires after an hour**. A target found days later is not a
returning visitor; it is a stale redirect that yanks somebody out of whatever they were doing.

**`share_events` records no user id, no IP, no user agent, no referrer.** These readers have no
account and agreed to nothing, so "how many" is the only defensible question. It is a table
rather than a counter because "opened 40 times, saved twice" and "opened twice, saved twice" are
very different products and a counter cannot separate them afterwards.

**`POST /api/share/event` is unauthenticated on purpose.** Requiring auth would count only the
half of the funnel that already converted. Both fields are closed vocabularies and the slug is
stripped, so the worst an abuser gets is an inflated count on a page they already had.

**Recording never raises.** Instrumentation must not be able to break the thing it measures. Note
the consequence: a `200` from `/api/share/event` does **not** prove the row was written. To
verify the write path, query the table.

### A dead vote code must be checked for EVERYONE (2026-09-06)

Five attempts. The first four were each a real fix in a place the reported
failure never reached, and the reason is worth keeping.

`isDeadVote` was nested inside `if (configComplete(loadConfig()))`. A link tapped
from Messages opens in Safari, which has no MenuCaptain config, so the whole
block was skipped and the dead-code list was never consulted - while sitting in
that same browser's storage, correctly populated, because `markVoteDead` runs on
both paths. The answer was always there; only the question was missing.

**The diagnostic that finally settled it was a screenshot with no Back button.**
The in-app overlay has one; the standalone guest ballot does not. That told us
which of the two paths was actually running, which four rounds of reasoning had
not. When a fix "doesn't work", establish which code path the user is on before
writing another one.

### Signature is not a tag; off-menu is not a menu (2026-09-06)

Two shapes of local knowledge, deliberately stored apart from the obvious place.

**`sig` sits beside the menu item, not in `tags`.** Tags drive the dietary
filter, so a signature in there would appear as a chip next to "gluten-free" -
wrong as a filter and wrong as a label.

**Off-menu items live on the PLACE (`r.offmenu`), not on a menu.** A bar with a
main menu, a brunch menu and a drinks list has one set of things that are on
none of them. They join `dishPool` so a thing you learned about can be logged
without retyping it, and each entry is dated with a "Still true" tap because
this is the type where being wrong is most expensive: a stale tip sends somebody
to ask a bartender, out loud, for something that no longer exists.

**Not built, deliberately: the community pool.** Same data model, so it is an
addition later rather than a rewrite. Building moderation, reporting, staleness
and abuse handling for public commentary about real businesses helps nobody
while there is no crowd to fill it.

### "I had this" starts today's visit (2026-09-06)

Marking a dish from the menu writes it to today's visit at that place, creating
the visit if there is not one. That is not a side effect to be nervous about:
you are sitting in the restaurant reading its menu saying you ordered something,
which is what a visit is. Rating and notes stay empty so the record claims only
what is known, and a dish already listed has its note updated rather than being
added twice.

### Dish photos go through the one upload path (2026-09-06)

Pending dish photos resolve at save exactly like visit photos and receipts -
existing paths pass through, pending blobs get a stable path and join the same
`pendingUploads` queue. One mechanism, so the 60-second timeout and the
"Photo 1 of 3" progress apply to them for free and there is no second uploader
to keep in step.

**UI state is kept off the dish object.** A half-resized blob with an object URL
is not saved data; paths are written only at save, so a failed save leaves
nothing pointing at files that were never uploaded.

### The in-app guide is the source of truth; the .md is generated (2026-09-13)

**Amended 2026-09-26:** there was a THIRD copy, in Dropbox under Guides_Help, that nobody
regenerated - three months stale. `export_help.js` now writes it from the same render, best
effort, so it cannot drift again. The Dropbox write failing must never fail a build that has
already produced the repo copy. A copy nothing regenerates is a copy that is wrong; the only
question is how wrong.

The user guide existed twice: `HELP_DOC` inside `index.html` (what people read, under Settings)
and `menucaptain-help.md`, with a comment saying the .md was the source and to re-sync by hand.
**They drifted in both directions.** The in-app copy was far richer in most sections, while four
sections written from 2026-09-06 on (the vote, local knowledge, "I had this", dish photos) had gone
only into the .md, so no user had seen them.

**`HELP_DOC` is now the source.** Edit the guide there, then run `node export_help.js` in
`menucaptain-native-build`, which renders the web version and overwrites the .md. Never edit the
.md by hand.

**Rejected: making the .md the source.** `HELP_DOC` contains build-dependent text
(`${IS_NATIVE ? ...}` hides upgrade wording in the store build), which a plain Markdown file
cannot express.

### Arriving at a place offers the menus other diners left (2026-09-13)

"Already at the restaurant" ends on a "You're all set" screen. With no menu of your own there, it
offered only "Get the menu" (photograph, their site, a link) and never mentioned that a shared
menu might already exist. A code comment claimed the scan flow offered community menus; it never
did. The screen now checks the library and, if anything is there, leads with the same
`CommunityMenuPanel` the place page uses, with **Get a fresh menu instead** underneath.

Only menus somebody chose to share are in the library. A privately saved menu is never offered to
another user, so "I added menus there" does not mean another person will see them.

### An email link survives the sign-in (2026-09-13)

The email button opens `?open=shares` in a browser. A browser with no MenuCaptain sign-in showed
first-time setup, and signing in reloads the page, so the destination was lost and you landed on
Home. The destination is now parked with `rememberAfterSignup` (one-shot, one hour, known
destinations only) and the sign-in screen says why you are there. **The sign-in itself remains**:
a browser cannot see the installed app's session, and only universal links in the native build
remove that.

### "Visit logged" offers Share it (2026-09-13)

New visits only. It opens the same share sheet as the visit card, which states what is sent; it
does not share in one tap from a toast. Edits stay quiet until there is a reason otherwise.

### Every share link opens in the app for an account holder (2026-09-16)

Visits (1.421.0), votes (1.424.0), menus and lists (1.456.0) and group orders (1.458.0) all
follow one rule now: a device with an account opens the link as an overlay inside the app; a
device without one gets the public page. Group orders copy the vote fix whole - code stripped
before the first render, `sessionStorage` for a refresh, a `localStorage` list of dead codes
checked for every visitor - with their own keys (`mc_open_group`, `mc_dead_groups`) so a vote and
an order sharing a code cannot knock each other out. **Chris chose "into the app, on the order"**
over "only stop the stranding" and "jump straight to adding your own items".

### A shared place carries signature marks and off-menu tips (2026-09-16)

Both are labelled as the SENDER's word, not the restaurant's, with each tip's last-confirmed date.
That labelling is the safety of the feature. Signature is one key (`g`) per item because it rides
every item against the 80k payload ceiling; off-menu is capped at eight.

### Places filters are pickers, not button walls (2026-09-16)

City, Cuisine and Sort are one row of buttons that open `PickerSheet` (the + menu's bottom-sheet
look), most-used first, with search past ten options. Chris chose this over "show six, hide the
rest" and over folding filters into search. Non-food Google types (`NOT_A_CUISINE`: Golf Course,
Point Of Interest, ...) are left out of the cuisine list only; the places stay under All cuisines,
and nothing stored is changed.

**Date order is its own drop-down (1.463.0).** Chris rejected newest/oldest living inside Sort,
and chose a separate Date control (Any / Newest first / Oldest first) over a "sort by + order"
pair. A date choice overrides Sort; picking any Sort option resets Date to Any, so the last
control touched always wins.

### "In their words" is not "About this place" (2026-09-16)

A menu scan now also returns `house_story`: text the menu prints about the restaurant itself,
verbatim, capped at 1,500 characters, dropped if under 40, and never invented. It is stored on
the place (`house_story`, `house_story_at`), and a later scan with a story replaces it.

**It is deliberately a separate field from `story` (About this place).** `story` is the user's
own word and travels in the share payload; `house_story` is the restaurant's marketing and its
copyrighted text, so it is private and is NOT in `buildPlacePayload`. Chris chose this over
filling About this place automatically and over keeping it manual. Both cards carry an info icon
instead of explanatory text, at his request.

### Show English on a menu in another language (2026-10-07, app 1.491.0 / backend 0.128.0)

Chris asked how the app handles a restaurant in Spain with Spanish menus. Reading worked and Help me
order / Explain the menu answered in English, but there was no English menu, and **neither digitizer
said anything about language**, so a scan could drift into translating on its own. Decided with him:
translate on tap.

- **Both digitizers** (`digitizeMenu`, `digitizeMenuFromText`) now carry a LANGUAGE rule: keep the
  printed wording, never translate. The menu is the record; English is a separate layer.
- **`translateMenu`**: one relay call per batch of up to ~120 dishes (section boundaries), task
  `translate_menu` (Sonnet 5, routed in backend 0.128.0). Every line goes out with an id (`s2`, `s2i5`)
  and only ids the app sent are accepted back.
- **Stored as `menu.translation = {lang, at, sec:{origSectionName: en}, item:{trKey(name, desc): [enName,
  enDesc]}}`, keyed by ORIGINAL wording, never by position.** Renaming, splitting or reordering can then
  never attach the wrong English; a changed dish just shows none. Positional keys were the road not
  taken: smaller, but silently wrong the first time anything moves.
- Toggle offered when `menuLooksForeign` (30%+ of dishes carry accented letters or es/fr/it/de/pt
  function words) or a translation exists; a translation that comes back `en` marks the menu English
  and hides the toggle for good. Preference remembered per device (`mc_menu_en`).
- Search matches the English. Refresh drops the translation (content replaced); split carries it, and
  a split into an existing menu merges both (`mergeTranslation`).
- **Not yet translated:** shared menus, published pages and the group-order guest page still show the
  original only.
- Verified: 23 checks on the real code with a stand-in relay; rendered on the real stylesheet.

### The server watches its own Firecrawl credits (2026-10-06, backend 0.127.0)

Firecrawl's free 1,000 monthly credits back the menu-from-link fallback. Claude sessions using the
Firecrawl connector burned them to about 15% before anyone noticed (the connector is now off for
sessions; see the `firecrawl-credits-reserved-for-menucaptain` memory). Nobody could read the balance
without handling the key, which lives only in Railway.

`_fc_credit_loop` reads `GET https://api.firecrawl.dev/v2/team/credit-usage` at startup and every
12 hours; `[FIRECRAWL]` log lines carry remaining / plan / period end; `/health` carries only
`menu_link_credits` = ok / low / out / unknown (**exact numbers on the public page was the road not
taken**). Low = under 25% of plan or under 100. Firecrawl's docs are silent on whether the check costs
a credit, so startup measures it (two checks 60s apart): **measured 0**. A 402 from any of the three
scrape call sites flips the state to "out" at once via `_fc_note_refusal`. When credits run out,
imports from hard sites fall back to the normal can't-read path, which offers a screenshot; nothing
crashes. First reading: **142 of 1,000, period ends 2026-10-25 19:35 UTC**. Verified: 17 checks on
the real code with a stand-in Firecrawl, then the live log.

### Refresh dates the menu today; no fake "Main" note; "Edit dishes" (2026-10-04, 1.490.0)

- **Refresh keeps the old date - fixed.** The re-scan branch set `captured_date: presetMenu.captured_date`,
  so a menu pulled in October read "Captured May 30". No recorded reason existed. Now
  `result.captured_date || todayISO()`. **Do not use `last_updated` for this**: tag toggles, renames and
  photos bump it, so it means "last touched". Splits still carry the source's date (they move content,
  they do not re-capture it).
- **"Note from Christopher: Main".** `groupCreate` sends `title: menu.label`; `title` is also the quick
  order's typed note, and the guest page rendered it as "Note from <host>". Fixed on the READING side
  (`hostNote` in GroupOrderGuest: a title equal to `menu_snapshot.label` is no note) so open orders are
  covered and the host's Active group orders list keeps showing which menu. The vote page's `title` is a
  real question and untouched.
- **"Edit names & tags" -> "Edit dishes"**, with "Names, signature dish, diet tags" beside it; the old
  label hid the Signature star it also controls.
- Group orders expire 24 hours after creation: `group_orders.expires_at` defaults to
  `now() + '24:00:00'` (read from the live schema 2026-10-04 with the Supabase plugin). The host's open
  orders list is the **Active group orders** card on Home and You.

### Rename a menu by tapping its name; a mini header on the menu screen (2026-10-03, 1.489.0)

Chris could not find how to rename a menu titled just "Menu". The row pencil had done it for
months, but it was the only unlabelled button among labelled ones, and a bare pencil reads as
"edit the dishes". **The title is now the control** (`.title-btn`: inherits the heading's type,
trailing pencil is the only affordance, `aria-expanded` follows the rename card). Road not taken:
labelling the row button, rejected because that row already wrapped the date on a phone.

He then asked for "a distinguishable mini header". Two options were rendered on the real
stylesheet (accent eyebrow in the top bar vs a tinted card); **he picked the tinted card**
(`.menu-head`): place + captured date in the `.menu-row` tint with the book circle, so the menu
screen looks like opening the card you tapped on the place page. Buttons got their own wrapping
row; the date no longer wraps. The eyebrow was the road not taken: more compact and sticky, but
quieter. A render harness for this screen lives in the session scratchpad, served by the
`menucaptain-harness` entry in the Claude Code folder's `.claude/launch.json`.

### 1.488.0: a raw NUL byte, and a blank strip in the store app (2026-09-29)

`aggregatePicks` keyed its Map on section + a **literal 0x00 byte** + item. Right intent (a
separator no dish name contains), identical runtime value to the escape, so no behaviour change;
the real function sliced from before and after returned identical output. But the byte made
`grep` treat the whole file as binary and print "Binary file matches" instead of lines, which
silently hid results during a search, and would blind any audit tool that greps index.html. Now
the `\u0000` escape; the file has no control bytes. **Check for this after any Python patch
that writes an escape**: `\0`, `\b` and friends become real bytes inside a normal Python string.

Also found: Home wrapped `InstallHint` in a div with a 13px margin. `InstallHint` renders
nothing under Capacitor, but the wrapper still drew a blank band in the native app. Gated on
`!IS_NATIVE`. The rest of the "hide Add to Home Screen in the store app" roadmap item was
already done.

This was also the first ship through the promo refresh step: the builder flagged 1.488.0 as not
yet reviewed, it needed no inventory line, and the stamp moved to 1.488.0.

### The promo brief rebuilds itself every ship (2026-09-29)

Chris wanted the promo "always up-to-date as we're making changes". Decided with him: one page,
three parts, refreshed every ship, Claude drafts and Chris corrects. Built as
`MenuCaptain Promo/make_living_promo.py` + `living-promo-template.html`, published to the
existing promo artifact so the link did not change.

**What regenerates:** the live-status strip (repo versions checked against what the site and the
server report) and What's new, which is **every frontend version bump in its commit subject**.
Frontend only, and that is the privacy design: server-only work (the webhook guard, the function
grants) never bumps the frontend, so it cannot reach a page shared by link. A structural filter,
not a deny-list. The generator also refuses to write if the page would contain a server hostname
or an email address; both checks were proven to fire against copies.

**What stays written:** inventory, cuts, supers, do-not-film. The road not taken was generating
the inventory too: never stale, reads worse, and cannot judge what deserves screen time. The
template carries `data-inventory-as-of`; anything shipped after it is flagged on the page and
printed by the script, which is the check that stops the written half drifting the way the
.md brief drifted three weeks.

**An error found in the old inventory:** "Share a visit" said what you ordered stays private.
Shared visits have always carried dish names (the payload comment was corrected in 1.459.0 but
the promo copy never was). It now says what is really withheld: private notes and what you paid.
Six lines were drafted for 1.474 to 1.487 for Chris to correct. **About this place's Suggest from
the web is listed but untagged**, because it has not yet made a real call.

The old `MenuCaptain-Promo-Brief-2026-09-06.md` is superseded and marked so.

**Sharing is Chris's setting:** the artifact is shared by link, but viewers see a pinned earlier
version, so people he sent it to will not see updates until the pin moves to the live version
(page's Share menu).

### The Stripe webhook now applies only OUR subscriptions (2026-09-28)

FitnessCaptain Pro sells through the same MilSpo Life Stripe account (Chris, 2026-09-28), and
Stripe delivers every event of a subscribed type to **every endpoint on the account**. Found by
the FitnessCaptain session reading our webhook; verified here before acting.

Mostly junk rows keyed by a user id from another Supabase project. **The case that is not merely
untidy**, and which that session did not flag: `customer.subscription.updated/deleted` with no
metadata falls back to `_user_for_customer`. One person buying both apps with one email is ONE
Stripe customer, so cancelling FitnessCaptain would have flipped their MenuCaptain row to
cancelled. The guard runs before that fallback.

`_is_our_subscription` accepts on any one of: the price is ours, the user is already in our
subscriptions table, or the event carries `app=menucaptain` (checkouts now set it on both the
session and the subscription).

**The middle rule is the correction to the suggestion.** Price-only was proposed; it breaks the
day `STRIPE_PRICE_MONTHLY` points at the .99 price, because existing .99 subscribers would
stop matching and silently stop updating. Relevant to `hold/price-3.99`.

**Both degradations accept rather than refuse**, and log: with no prices configured the guard
cannot tell ours from anyone else's, and a failed ownership lookup is not evidence. Refusing
everything would break billing silently, which is worse than the pollution this prevents - the
opposite of the usual fail-closed default, because here the guard is the thing that can be wrong.

### Database functions are locked to the backend (2026-09-29)

The FitnessCaptain session also reported that its `record_ai_usage` was executable by the `anon`
role. **Ours was too, and so was every other public function**: `record_ai_usage`,
`record_places_usage`, `set_updated_at`, `rls_auto_enable` all answered `anon_can_run = true`.
Anyone with the public anon key could have pushed `system_meter` past the monthly AI breaker and
switched AI off for every user, or done the same to the Places breaker. The July RLS work never
covered this: **RLS protects tables, not functions.**

Fixed live 2026-09-29 by Chris in the SQL editor; the statements are now in
`dining-captain-backend/sql/function_grants.sql`. Blanket revoke from `public, anon,
authenticated`, explicit grant to `service_role`, and schema-level default privileges.

**Correction, 2026-10-06: those default privileges did NOT make later functions start locked**, as
this entry originally said. A per-schema default can only add to the global default, and Postgres's
built-in global default grants EXECUTE on new functions to PUBLIC (which includes anon). Verified
read-only against `pg_default_acl`: postgres has a public-schema entry (postgres, service_role) and
no global entry. Found by the portfolio overview session, which had already applied the global fix
to the other nine projects. The missing line is
`alter default privileges for role postgres revoke execute on functions from public;`, now in
`function_grants.sql` with a rolled-back probe that proves it. Existing functions were never
affected. **Applied live 2026-10-06** with Chris's yes, through the Supabase plugin, as migration
`default_function_privileges_private`; probe: `anon=f authenticated=f service_role=t`; the four
existing functions re-checked false/true and no probe function was left behind.

**The grant half is the dangerous one to forget.** Whether `service_role` holds EXECUTE explicitly
or through PUBLIC depends on the project's default privileges, and this project already surprised
us on tables. If a revoke took the backend's access too, nothing would show: `record_usage` and
`record_places_usage` log and swallow by design, so metering would just stop and the breakers
would never trip. **Verified both halves**: anon false AND service_role true on all four. A
before/after on `ai_usage` was tried first and could not tell "no AI call yet" from "metering
broken"; the two-column privilege check settles it without needing a call.

The frontend calls no RPCs (no `.rpc(` or `/rest/v1/rpc` in index.html), so nothing in the app
depended on the anon grant. Trigger functions are unaffected: EXECUTE is checked when a trigger is
created, not when it fires.

### A wrong email is caught at sign-up, all of it (2026-09-28)

With confirmation off, a misspelt address makes an account that works perfectly until a password
reset goes to an address that does not exist. The confirm-email box catches a random slip but not
the SAME slip typed twice, nor autofill filling both boxes wrongly.

**Two layers, sign-up only:**
- **`emailDomainSuggestion`** - "Did you mean gmail.com?", live under the Email field. Matches
  against a list of real providers using **optimal string alignment distance**, so two swapped
  neighbours count as ONE slip. Plain edit distance scored "gamil" as two changes, tied it with
  mail.com and suggested nothing - on the commonest way fingers miss. Real providers near big names
  (gmx.com, proton.me, pm.me, me.com, att.net) are listed and never touched; distance 1 for short
  domains, 2 for longer; a tie suggests nothing. 32 checks.
- **A read-back card** before the account is created - Chris's idea. No rule can tell "chirs@" from
  "chris@"; people check an address they are SHOWN more carefully than one they retype. The domain
  correction sits on the same card, so it is one moment of checking, not two.

**The card's primary button is the correction when there is one.** The first render made the big
accent button "Yes, that's right" with the fix in a quiet button above it - a thumb goes to the
accent, so the card would have confirmed the very slip it exists to catch. Caught by rendering it.

**Sign-up only, deliberately:** on sign-in the account itself may carry the misspelling, and
"correcting" it would send the person to an account that does not exist.

**"Already registered" is now good news.** Somebody who signed up, thought it failed (no email) and
tried again got Supabase's raw "User already registered". Now the app switches to sign-in with the
address kept and says the account exists. A second attempt with a CORRECTED address is a separate
account and simply works; the misspelt one is a harmless orphan to delete in Supabase.

`signUp(confirmed)` treats only a strict `true` as a yes: wired to onClick it receives the click
event, which must not count.

### Sign-up sends no email, and now says so (2026-09-28)

Chris reported people signing up who "checked spam and never got the email". Supabase's public
settings (`/auth/v1/settings`) report **`mailer_autoconfirm: true`** - email confirmation is OFF, so
a new account is signed straight in and **no email is sent at all**. There is nothing to arrive.
People expect one because nearly every app sends one.

The three things a "missing email" report actually is, in the order to check them:
1. **Waiting for a confirmation that does not exist** - usually already signed in.
2. **Signed up in the browser, then opened the home-screen app** - iOS gives each its own
   storage, so the app shows sign-in and it looks as though sign-up failed.
3. **A password-reset email**, the one email the app genuinely sends (via Resend). Real causes:
   a typo'd address, the Gmail Updates tab, work-mail quarantine, or **Resend suppressing an
   address that once bounced** - which only the Resend dashboard shows.

Support playbook: ask "did the app let you in after you signed up?"; if genuinely locked out,
check Resend's logs for the address and Supabase > Authentication > Users for the account.

**Built (Chris picked one of four):** the sign-up screen now says there is no confirmation email to
wait for, and a one-time message says it again the moment a new account is in (a localStorage flag
carries it across the sign-in reload). The guide's troubleshooting explains cause #2. **Offered and
not built:** a browser-vs-app line on the sign-in screen, a better reset-email confirmation screen,
and Sign in with Apple.

**Stale comment corrected by this finding:** the sign-up code still carries a "confirmation is on"
branch and copy ("we sent a confirmation link"). It is unreachable while autoconfirm is on, and
left in place deliberately so that turning confirmation back on in Supabase still works.

### About this place can be drafted from the web, with sources (2026-09-28)

`POST /api/place/about` runs Claude (task `place_about`, Sonnet 5, effort medium) with the
server-side **web search tool** (`web_search_20260209`, `max_uses` 3) and returns two parts - what
the place says about itself, and what people say - plus the sources used. The editor's **Suggest
from the web** APPENDS the draft to the About box; it never replaces what the user wrote, and
nothing saves until the place is saved. Sources persist as `story_sources` / `story_sourced_at`
and are listed, dated, under the About card. They are **not** in the share payload.

**How we got here, because the road not taken matters.** Chris first asked for an AI to "find
something unique". Ungrounded, that invents founders and dishes for small places, and About this
place travels in shares under the user's name. Then "what people are saying" ran into the
2026-09-06 licensing finding - Google forbids caching review content; Yelp, Foursquare and Reddit
forbid derived datasets - which ruled out harvesting reviews into a saved field. Chris clarified
he meant **an AI web search**, which is a different act: a licensed search tool reads public
pages and the model writes a short cited summary, the way Claude, Perplexity and ChatGPT answer
the same question. That is standard practice and a reasonable position, not a legal guarantee.

**Priced before building** from Anthropic's pricing page, read 2026-09-28: web search **$10 per
1,000 searches**, plus results billed as input tokens; Sonnet 5 $2 / $10 per MTok. Estimated
**7-11 cents a tap**, about three ordinary calls. **It counts as three against the allowance**
(Chris's call - the free tier is metered by spend), recorded as one usage row carrying the
tokens and the search cost (`record_usage` gained `extra_cost` so the monthly breaker sees real
spend) plus two rows carrying only the count. `_place_about_room` refuses up front when the call
would not fit - at 73 of 75 a three-call action would otherwise finish at 76.

**Four guards, each for a reason:**
- **Only sources the search actually returned survive.** Any URL the model names that did not
  come back from the search is dropped: a model invents a plausible link as easily as a plausible
  fact.
- **Nothing is better than padding.** It is told to return null for a part it cannot support.
- **Same place, same town.** Small places share names with others elsewhere.
- **Summarise, don't copy** - a few words at most from any one source.

A paused server-tool turn (`pause_turn`) is resumed, bounded at four rounds. Usage is recorded
in `finally`, so a failure part way through still records the searches that were billed.

**Not verified live before shipping:** the API key lives only in Railway, so the endpoint was
tested with a stand-in client (24 checks: both parts, a fabricated source dropped, tool and
effort settings, three usage rows with 2 cents on the first, pause_turn resume summing tokens,
an error-shaped search result, nothing found, prose instead of JSON, 73 vs 72 of 75, a blank
name). The first real tap is the first live call; its cost should be read from the `[ABOUT]`
and `[COST]` log lines and compared with the 7-11 cent estimate.

### A place's menu comes first and looks like a menu (2026-09-28)

Chris opened a place and could not quickly find its menu. Under "Menus (1)" the order was the
panel of menus other diners shared, the dietary chips, the Not-on-the-menu card, and only then the
menu - **fourth**, labelled "Main" with nothing marking it as a menu. "Main" alone reads as a
course or a dining room.

Now: your menus come first, each led by a book icon in an accent circle so the row reads as a
menu before the label is read. `menuDisplayLabel` shows a label of exactly "Main" as **"Main
menu"** and leaves every other label alone - a blanket "+ menu" suffix gives "Wine List menu".
The off-menu card follows the menus, renamed **"Not on the menu / specials"** because a special
is the thing people most want to record there and the old name did not say so. The panel of
menus other diners left drops below your own once you have one; with none it stays on top,
which keeps the 2026-09-13 decision that arriving at a place offers what others left.

**Accent (1.485.0).** Chris picked option A of three rendered mockups: your menu cards carry a
faint accent tint and edge, and the Menus heading gets the same accent bar as form section
headers. Tint via color-mix on var(--accent), so it follows the theme; fixed Warm Brown values
are declared first as the fallback. The rejected options were one tinted panel around all menus
(a box around boxes) and a coloured heading alone (menus still looked like every other card).

### Add a menu asks what you have; links no app may read are caught (2026-09-28)

**The labels.** The three routes were named by mechanism - "Choose / take photos", "Link to a
menu online" - under a card that only talked about photos, so the reader had to translate each
into "is that what I've got?". Chris suggested "I have a link to paste" and the idea generalises:
the screen now asks **What do you have?** and the options answer it - *Nothing yet - find it for
me*, *I have the menu or a screenshot*, *I have a link to paste*. The iPhone slow-photo warning
moved from permanent fine print to the moment it is actually happening.

**The dead ends.** Chris pasted a Google listing for a coffee shop whose menu he could plainly see.
The honest position, which took two corrections to reach:
- It is **not impossible** to read. Google search, Yelp and TripAdvisor are readable with a
  residential render. For Google and the review sites the reason not to is **their terms**, which
  an App Store app has to respect. Facebook and Instagram add a login wall.
- The Places API **does not help**. It has no menu field; what we request is name, address, phone,
  website, rating, price, hours, summary, status and photos. The typed menu on a Google listing
  comes from the owner's Business Profile and is only available to that owner. Following the
  listing's *website* works for places that have one - Pink Coffee's is a Facebook page.
- What the person CAN do is capture what is on their own screen: **screenshot it and add it as a
  photo**. That is theirs, for their own notebook, exactly like photographing a paper menu.

So a pasted Google, Facebook, Instagram, Yelp or TripAdvisor link is caught **on the phone, before
any request**, and gets a card saying why with a **Choose the screenshot** button. "Find it for me"
catches the same thing when a place's only website is a Facebook page. Previously the Google case
cost two paid renders (the bot check reads as a block, which escalates to Firecrawl then stealth)
and ended in a generic no-menu message.

**Scoped to search and profile PATHS, never whole domains** - a cafe genuinely can host a menu on
`sites.google.com` or share a PDF from Drive or Docs, and those must keep working. The backend
refuses the same list as a second line (`_MENU_DEAD_ENDS`), for older app versions and anything
else that reaches the endpoint directly. **Two copies of one rule**: a parity script runs the real
backend function over the same 26 cases as the app's test, including lookalikes (wix.com is not
x.com, myfb.com is not fb.com). Change one list, change both.

### A public About page, in the promo sheet's language (2026-09-27)

Somebody opening a shared visit got a meal and a Create account button and nothing between them.
Chris shared a dinner with friends who wanted to know what the app was, and the only answer
available was to explain it himself by text message. `menucaptain.com/?about` is now that answer,
linked from every shared page beside the sign-in line.

**It was on the wrong bar first (1.478.0).** A shared VISIT has its own sticky footer, separate
from the SignupBridge that menus and lists use, so the one page Chris actually sends friends never
showed the link. The comment three lines from that edit records the SAME miss in 1.434.0: two CTA
surfaces, and a change to one keeps looking like a change to both. Check both whenever either
changes.

**Then it was fine print (1.479.0).** A text link under a paragraph, beside a large orange button,
in the smallest type on the page - everything else in that bar aims at somebody who has already
decided. The question now gets a branded CARD at the END of the visit, in the promo language, and
the fine-print link is gone rather than duplicated. The footer keeps its single job.

**And at the foot of the page it may as well not have existed (1.481.0).** Chris opened a fresh
private window and still could not find it: nobody scrolls somebody else's 94-item menu to the
bottom. It now sits where the VISIT ends and the menu begins - after Directions - which is the
moment a reader has finished the thing they were sent. Three placements in three versions, each
one only visible as wrong once it was in front of a real reader.

**It lives in the app, not anywhere else.** That is the only copy that cannot fall behind the
product, and it is on his own domain rather than a hosting service's.

**Deliberately not the promo brief**, which carries shot lists, a do-not-film list and an
investor line. Different audience entirely: this is for a friend who was handed one meal.

**The first cut was five grey cards of prose** - accurate and completely flat. Chris asked why it
did not look like the promo work, and he was right: a signed-off design for exactly this job
already existed in `MenuCaptain Promo/_promo_print.html` and **I had not looked at it**. The page
now ports that language - the helm mark copied verbatim, the two-tone Fraunces wordmark, the
italic tagline over an accent rule, tiles led by an outline icon in an accent circle, the italic
pull-quote, the pill CTA.

Two deliberate departures from the print sheet: its icons came from a Tabler webfont over a CDN,
and this uses the app's own icon set - same stroked-outline style, no network - and the tiles are
one column on a phone, because most people meeting this page are opening a link from a text.

**The rule this is the second instance of: check for the signed-off sibling BEFORE building, not
after being asked why it looks different.**

### A shared visit collapsed Loved into Again (2026-09-27)

The app has three verdicts and the guide calls them its heart: **Loved** for a standout, **Again**
for something solid, **Skip** for neither. In the app they are even styled apart, pink against
amber.

The share payload set one flag for both and captioned the lot "marks the ones they would order
again", so a dish somebody adored and a dish they merely liked arrived identical, under a label
that was wrong for the first. Chris caught it reading his own shared visit.

The payload now says which: **y:2 loved, y:1 again** - one extra digit per positive dish - and the
shared page uses the same two chip styles the app already uses, with a legend naming only the
marks actually present.

**Older links only ever set y:1, so they keep reading as Again.** That is the safer direction to
be wrong in: it under-claims rather than putting a word in somebody's mouth.

### The check already knew what the table ordered (2026-09-27)

Chris split a five-way dinner item by item, then opened the visit and found "What you had" empty.
Splitting **has always recorded** which line item each person was ticked under - it cannot compute
what anyone owes otherwise - and that map is saved on the visit in `split.inputs.assign`. Nothing
ever read it back.

`splitWhoHadWhat(split)` derives the table's order from what is already stored, so it works on
every split ever taken rather than only future ones. **Nothing new is persisted.**

A visit with assignments offers **Bring in what the table ordered**. It asks which of the names on
the check is you, because **a split has no notion of "me"** - the names are whatever suited the
table that night - and guessing would put somebody else's dinner in your history. Your items
become your dishes; everyone else's render read-only. That division is the point: "What you had"
is yours, and what the table had is a different fact.

**Only companions were ever seeded from a split, and only on a NEW visit.** Chris was on an
existing visit, so even that did not apply.

**Name matching had to be rebuilt, not reused.** `likelySamePerson` compares FIRST names, so it
catches "Kristin" against "Kristin Gramlich" and misses "Witherspoon" against "David Witherspoon"
- and a surname is exactly what people write on a check. `splitNameScore` counts whole words
shared and the best score wins.

**Caught by a test, not by reading:** the first cut refused whenever more than one candidate
matched at all. Correct for "Witherspoon" against two Witherspoons, wrong for "Tori Witherspoon"
against the same two - it matched David on the surname and gave up on a name that could not be
clearer. Ambiguity is a **tie**, not merely more than one candidate.

### Two companions who are one person can be merged (2026-09-25)

Chris's companions list showed **Kristin Gramlich @kristingramlich, 19 visits** and **Kristin, 6
visits** - the same person, split because he tagged her by first name for months before she
signed up. `companionKey` keys on `user_id` when there is one and on the lowercased name when
there is not, so an account arriving mid-history splits that person in two. Nothing in the app
could join them; the only remedy was re-tagging six visits by hand.

**This is structural, not a one-off.** Every unlinked name on that list splits the same way the
day its owner signs up.

`mergeCompanions(visits, fromKey, to)` rewrites the absorbed tags to carry the target's account
and returns a new visits array, or **null when nothing matched** - so the caller can tell "merged"
from "there was nothing to merge" instead of committing a no-op. A visit already carrying the
target keeps one of them; the merge must not tag one person twice on one meal.

Two ways in, per Chris: **"Same person as..."** on anyone, and a **suggestion on the row** driven
by `likelySamePerson` - written for the guest-order work in August and matching exactly this case.
It only suggests **from an unlinked row to a linked one**, the direction that gains an account.

**It suggests and never applies.** Two people genuinely can share a first name, and undoing a
wrong merge means re-tagging every visit. Chris was offered auto-merge and did not take it. The
confirm names both people, the direction and the count, and says plainly that undoing is manual.

### A place is rated on Food, Service and Atmosphere (2026-09-24)

Three half-star raters instead of one. A single overall still exists, because Places sorting,
"highest-rated place", the export and the share card all need one number, and it is **weighted at
Chris's direction: food 0.5, service 0.3, atmosphere 0.2** - a meal is mostly the food.

**Weights renormalise over the parts actually set.** Rate only Food four stars and the place
scores four, not two. The alternative - treating an unrated part as zero - would quietly punish
every place somebody had not finished rating, which is most of them.

**Existing ratings are untouched.** `placeRating` tries the weighted parts, then the old
`my_rating`, then the latest rated visit. An existing 5 stays a 5 until a part is set; nothing was
back-filled, so the app never claims somebody rated three things when they rated one.

**Chris asked for a typed exact number and then withdrew it** once the weighting was settled:
"now that we are averaging them I don't need to type the number". Half-star taps only. The overall
is displayed and never editable - a field you can type into invites it to disagree with its own
parts.

Two clean-ups the change forced, both worth having on their own:
- **Four readers, one rule.** History sorting, Places sorting, the export and `placeRating` each
  carried their own copy of "my_rating wins, else fall back to a visit". Four copies is four
  chances to disagree about what a place scores, and adding a weighting would have meant editing
  all four correctly. They all call `placeRating` now.
- **Two star implementations, one component.** `StarRater` and a copy inlined in the visit form.
  Both screens use `PlaceRatingFields` now. The inlined copy also still had the unfilled-star bug
  fixed in 1.471.0, which is what two implementations gets you.

The guide paragraph for this was already wrong before today - it said you rate each VISIT and that
the number shown is an average labelled "avg", neither true since the rating moved onto the place.
Rewritten rather than left.

### A lit star is filled, and counts say the right word (2026-09-24)

Every glyph in the icon set is drawn as a stroked outline with `fill:none`, so a **lit star was an
amber outline**. Five out of five rendered as five empty stars beside a "5" - the number and the
picture said opposite things, which is what made it visible in Chris's screenshot. `Icon` takes a
`fill` now; only the star passes one.

Separately, "1 visit(s)". `countLabel(n, one, many)` fixes the four places a **count** is on
screen. Deliberately not applied to phrases with no number - "contribute your menu(s)" is a
genuine either, not a pluralisation bug, and rewriting those would be churn.

Both were noticed while reading the recap card for the two bugs below, and neither was asked for
until Chris said to fix everything raised.

### "Most loved dish" was crowning the alphabet (2026-09-24)

Chris's recap read **Most loved dish: Americano**. The list under it was Americano, Black
Manhattan, Black Panther, Blackened Chicken Sandwich, Cadillac Margarita, Carajillo Aveo - strict
alphabetical order, and no chip carried a `xN`. Every count was 1, so the **tiebreak** picked the
winner and the card was really showing "the positively-rated thing whose name sorts first".

A favourite now needs a **repeat**: `crown()` returns the top entry only when its count is above
1. That is the bar `myUsualAt` already sets for "your usual here", so the app means one thing by
favourite. Below the bar the list still shows, relabelled "Dishes you liked" with a line saying
what would promote one. Showing the list was never the problem; calling its first row a favourite
was.

### Drinks are counted apart from food (2026-09-24)

A logged dish stores a name, a note and a verdict - nothing said whether it was food. Cocktails
therefore competed to be the most loved *dish*, which is how a Black Manhattan ended up on that
card.

The menu already knew: the item came out of a Cocktails section. **`addDish` now records that
section** on the dish, and `dishIsDrink` falls back to looking the name up in that restaurant's
menus when it is absent - so history logged before today sorts itself out with no migration.

**Matched on the SECTION name, never the dish name.** "Arnold Palmer", "Dark and Stormy" and
"French 75" are unwinnable by name, and a wrong guess relabels somebody's dinner. Unknown counts
as food for the same reason: a menu we cannot consult must not turn a meal into a nightcap.

### The Discover tab is now "You" (2026-09-24)

It holds Year in Food, the Food passport, People, the Leaderboard, Shares, Connections and splits
- every one of them the user's own record or their own people. Nothing in it discovers a
restaurant; the nearby search that does lives on another screen. Chris raised it himself.

**The internal key stays `"discover"`.** It is persisted in navigation state and used by deep
links; renaming a stored value to match a label is how you break the thing the label was meant to
clarify. Icon moved from the compass to people.

### One fold control on every menu (2026-09-24)

Four screens rendered a foldable menu and each had invented its own rule: your own menu opened
with the first two sections showing, a shared visit all closed, a group order closed only when it
was multi-menu or over twelve items, a shared menu page all open. Same object, four behaviours,
and nowhere to say "just show me everything".

`useMenuFold` + `MenuFoldBar` now serve all four. Three options, exactly as Chris specified:

- **One at a time** - the default. Opening a section closes the one that was open.
- **Expand all** - everything open; sections still fold individually from there.
- **Collapse all** - shuts everything **and returns to one at a time**. Chris's follow-up call:
  collapsing is how you get back to the top of a menu, so it should leave you in the mode that
  keeps you there. It is why there are only two persisted modes for three buttons.

**The mode is remembered per device, the open sections are not.** The mode is a reading
preference, like text size, so it rides `localStorage` (guarded both ways - it can throw in a
private window). Which sections happen to be open resets each time, because section index 3 means
a different course on the next menu.

A search still forces every section open wherever a screen has one - a hit inside a closed section
is a hit nobody finds. That is the only thing allowed to override the mode, and it stays
per-screen because only two of the four screens search.

Deleted along the way: the "first two sections" rule, the ">12 items or multi-menu" heuristic, and
two separate always-open defaults. Four fold implementations became one.


**Anchored (1.469.0).** The row sticks to the top of whatever is scrolling, so on a long expanded
menu the way back to a short list is one tap rather than a scroll to the top. One CSS rule covers
all four: every site puts the bar in a container padded 18px, and none has a sticky header INSIDE
its scroll area, so it sticks at 0 and bleeds 18px either side to let rows pass behind it.
### A closed group order offers to become a visit (2026-09-23)

A closed order already knows the place, the date, who was there and what each of them picked.
Closing now offers **Close and log this as a visit**, which opens the ordinary visit form
pre-filled. **Nothing is written without the host saving it** - orders get closed for plenty of
reasons that are not "we ate", and a silent write would put meals in the diary that never
happened. Chris chose the offer over automatic.

It reuses the `mc_logvisit_seed` channel and the `seedVisit` prop a shared visit already uses,
rather than adding a second way to open a pre-filled visit form. `seedVisit` gained `dishes`.

**The seed carries the place by NAME, not by id.** Of the four places that open the host screen,
one resumes a session by code and holds no restaurant object at all; an id would have left that
one unable to offer this. The reader resolves the name against places that have finished syncing,
and **drops the seed** if no place matches once places have loaded - a seed that cannot resolve
would otherwise retry on every render for ever.

Everyone who picked is seeded as a companion, the host included if they picked. There is no
reliable host marker in the picks, and the visit form is the review step, so the offer says to
check it rather than guessing.

### Group sessions are deleted 30 days after they expire (2026-09-23)

Until now **nothing deleted them**. An expired session was hidden from the UI, but the row, its
picks, its ballots, its view records and the guest names on all of those stayed indefinitely.
Those are other people's names sitting on a host's session, and "kept indefinitely" is not an
answer worth writing on a store privacy form.

A daily task started in `lifespan` sweeps in bounded batches. Chris chose 30 days: long enough to
still log last month's dinner, short enough that names do not accumulate without end.
`GROUP_RETENTION_DAYS` is env-overridable, so it can be tightened without a deploy.

**Children are deleted before the session, and the order matters.** None of the child tables
declare a foreign key, so nothing cascades. Crash halfway with the children gone and you have an
empty session the next sweep finds again; crash halfway with the *session* gone and the children
are orphans no sweep can reach, because every sweep starts from `group_orders`.

### Two sections that invite the wrong box get a panel each (2026-09-22)

On Edit visit, "Who was with you?" and "What you had" both had headings, but their controls are
the same shape - a box with an Add beside it - stacked in a continuous form. That adjacency put a
person in the dish list once already. 1.430.0 added a check that CATCHES the slip; `.secpanel`
removes the invitation, boxing each section so the eye cannot read past the boundary by accident.

**The panel is `--bg-2`, not the `--surface` a `.card` uses.** The first cut reused the card
colour and, rendered side by side against the old layout, the inputs inside disappeared into their
own container - a card normally holds text, and this one holds boxes. `--bg-2` is the step below
`--surface` in all five themes, so the panel recedes and its controls sit proud of it. Worth
remembering the next time a "reuse the card" instinct meets a container full of controls.

### Both estimate buttons name the same act (2026-09-22)

"New estimate from menu photo" sat beside "EST nutrition from DESCR": one act, two vocabularies,
and the longer one wrapped on a phone. It is now **EST nutrition from MENU PIC** - MENU PIC rather
than PHOTO because the button next to it is about the user's OWN photo, and PHOTO would name both.
The pair exists on **two** render paths (with and without icons) and both were changed; changing
one is how two screens end up calling the same thing different names.

### A saved menu can be split up (2026-09-22)

Splitting a scan into several menus existed only on the review screen ("Customize each section"),
which is too late the moment a menu is saved - and the web-menu fix above means one pull can now
bring back a restaurant's whole page, so a single saved menu holds dinner, lunch, drinks and
brunch at once.

**Split** sits beside Rename on the menu card: tick sections, name where they go, they leave.
`splitMenuSections()` is a pure function returning the whole replacement list for that
restaurant, or `null` when the move is not a move - which is what made it testable
(17 checks) without a browser.

Two rules it inherits rather than invents:
- A destination name matching a menu you already have **merges** into it. That is the same rule
  the scan review screen states, so the two places cannot disagree about what a repeated name
  means.
- Moving **every** section out is refused. That is a rename, and doing it as a split would leave
  an empty menu behind. The panel says so rather than silently disabling the button.

### A shared visit opens with the menu folded (2026-09-22)

The courses in a shared visit always folded; they just started open, so someone opening a link to
see what a friend ate scrolled a whole menu to get past it. Every named course now starts shut,
which turns the same block into a contents list: course names with their item counts, opening on
a tap.

A section with **no** name draws no header button, so folding it would put its items out of
reach. Those start open. `useState` takes an initializer function rather than a value, so the
fold map is computed once from the payload instead of on every render.

### The menu chunk is 20,000 characters, not 8,000 (2026-09-22)

`MENU_TEXT_ONE_PASS` was 8,000, chosen for the WAIT: the halves digitize in parallel, so eight
small calls finish in roughly the time of one. What that reasoning missed is that the allowance
counts **calls, not words** (`AI_CALL_CAPS` free = 75 lifetime), so a 199-item menu split eight
ways spent about eight of a free user's seventy-five on one import.

Chris chose the allowance over the wait: a big menu is now two or three calls and about fifty
seconds rather than eight calls and about twenty. 20,000 characters is roughly 6,000 tokens of
JSON, comfortably under the 16,000 the call asks for, and the `stop_reason === "max_tokens"`
re-split still catches a menu dense enough to overrun.

### A web menu is judged on what the page CLAIMS, not on what it shipped (2026-09-22)

A restaurant page can print its menu's section titles and leave the items for JavaScript to fill
in. The direct fetch then reads whichever section happened to be in the HTML, finds real prices
in it, and we accept that as the menu. Chris hit this on a Webflow site that printed 32 section
titles and shipped the items for exactly one: he saved the appetizers and nothing else, with no
sign anything was missing.

The old question was "did we find any prices", which a partly filled page answers yes. The new
one is "did we find prices for everything the page NAMES". A finished menu prices most of what it
lists, so its price markers outnumber its menu headings; a shell inverts that. Measured on the
reported page: **10 price markers against 54 menu headings as fetched, 349 against 237 once a
browser had filled it** (13 items versus 199). `_menu_heading_count()` counts headings that sit
inside menu markup, read from the MARKUP rather than the text, because what we need to know is
what the page promised and that survives when the items never arrive.

A page that looks like a shell is rendered through Firecrawl with `full=True`, using
`_firecrawl_render` so the same call returns the pictures too — a shell's dish photos are in the
rendered markup, never in what we fetched. The existing guard is unchanged: rendered text
replaces the fetched text only when it is at least as menu-like, so a bad render can never
clobber a good page.

**The road not taken:** counting empty containers. It reads like the obvious tell and it is
wrong — the same page after a browser filled it had *more* empty menu-ish divs (11,619) than the
shell did (794). Modern pages are full of empty divs. Measure the content, not the scaffolding.

**Known consequence, not yet addressed:** a whole 199-item menu is ~40k characters, and
`MENU_TEXT_ONE_PASS` (8,000) splits that into roughly eight AI calls. The quota counts CALLS, not
tokens (`AI_CALL_CAPS` free = 75 lifetime), so one big menu import now costs a free user about
eight of their seventy-five. Raising the chunk size trades latency for quota; the 8,000 figure
was a deliberate latency choice, so it is Chris's call and is on the open list.

### The email CTA is a link again (2026-09-03, reversing 2026-08)

It was turned into an instruction ("Open MenuCaptain on your phone to see it")
because on iOS a web link cannot open an installed home-screen app. That
reasoning was correct and the result was still wrong: the email became a dead
end with nothing to press.

It is a button again, with the two changes that make that defensible: it points
at the thing (`?open=shares`) rather than the front door, and the caveat is
stated rather than solved by deleting the button. **A link with a caveat beats
no link.**

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

**Controls named after their mechanism disappear.** Three instances so far, all
reported as "the feature is gone" when it never moved: the `auto` link on the
split screen, "New estimate from your photo" (which is how you add a photo), and
a nav bar whose only styled element was the ADD action. Name a control by what
the person gets, not by what the code does - and be especially careful with any
control that CHANGES LABEL between states, which is where all three hid.

**Free-text notes keep being put in single-line inputs.** Four found: the
off-menu note, the "how was it" comment, the vote note, and the dish note. A
comment you cannot read back while typing it is not worth having typed. If a
field can hold a sentence, it is a textarea.

**Never pipe the compile check into a `&&` chain.** On 2026-09-13 `node verify_compile.js 2>&1 |
tail -1 && git commit ... && git push` pushed a syntax error to production (1.453.0, live for a
few minutes). The check failed, but a pipeline's exit status is the LAST command's, and `tail`
succeeded - so the chain carried on. The same pattern had been used for weeks and simply never
failed before. Run the check on its own line and test its exit code before committing. `build.js`
in the native repo does exit non-zero on a bad compile, which is why the store bundle was not
committed that time.

**A corrupt git object in the native repo (2026-09-13).** A push failed with `corrupt loose object`
for the `www/app.js` blob written moments earlier; cause unknown. Repaired without losing anything:
confirm `git hash-object www/app.js` matches the named hash, move the bad object file out of
`.git/objects`, `git hash-object -w www/app.js`, `git fsck`, push.

**A comment describing behaviour is a claim, not a fact.** Twice now a comment asserted
something the code did not do: that the scan screen offered community menus, and that
`menucaptain-help.md` was the guide's source of truth. Both were believed and both caused real
misses. Check the code a comment describes before building on it.

**`fetch` has no timeout of its own.** Photo upload hung indefinitely on a weak connection until
an `AbortController` was added (60s per photo). Any new network call that a user waits on needs
the same treatment.

---

## What is open

**Blocked on Chris — nobody else can do these:**
- ~~iOS build machine~~ **resolved 2026-09-15: Chris bought a MacBook Pro.** Next: Xcode on it, then TestFlight
- Google Play Console registration and the Android release keystore
- Store listing details: subtitle, Google title, age rating, demo account
- Stripe prices, then `git merge hold/price-3.99`

**Known bugs, unfixed and deliberate about it:**

**Parked, with reasoning:**
- "Saved by N people" reported back to the sender. Proposed alongside the funnel work and
  deferred: it needs a per-slug count surfaced in the UI, and it is the weakest of the four
  ideas until the funnel numbers show anyone is opening these links at all.
- Reported: the share card image has empty black bands. NOT reproduced - `buildRestaurantCardBlob`
  draws on a tall scratch canvas and crops to the height actually used, so the PNG is trimmed to its
  content. The report came from another session looking at a rendered preview. Needs a screenshot
  of a real sent card before anything changes.

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
