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
| Web app | **1.530.0** | menucaptain.com (GitHub Pages), confirmed live |
| Backend | **0.145.0** | Railway, `/health` reports `db connected` |
| Native shell | **1.530.0** | built and pushed, **not yet submitted to any store** |

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

Then check no name is used that is never defined (a typo or a moved function compiles fine and
throws on the phone). It compares the working file with the last commit, so run it BEFORE committing:

```bash
cd /c/Users/cjgra/menucaptain-native-build && node verify_names.js
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

### A place in Malta with no town, and accent-blind place search (2026-10-15, app 1.530.0)

Chris, in Malta: he scanned two menus for Enchanté (Senglea) with the walk-away scan, "it said it
got in there ... but I don't see it". **The scans were fine**: both jobs done, opened and saved;
the server shows the place with 2 menus (Main, 9 sections / 53 dishes; Drinks, 17 / 201) and 1 visit.
Checked with aggregate and non-personal queries only. Two things could hide it, both fixed:
1. Its address "Triq Juan B Azzopardi, L-Isla ISL 1263, Malta". `cityFromAddress` knew no Maltese
   postcode (three letters, four digits, AFTER the town), so the place was saved with NO town, the
   only one of his 125 with an address but no town; a Places list filtered to a town hides it. Now
   read, **only when the address ends in Malta** (the shape is too loose elsewhere). The existing
   sync-time backfill fills a blank town from the address, so his record repairs itself on the
   next open; nothing was changed on the server.
2. Place search compared letters exactly, so "enchante" never found "Enchanté". The Places list,
   Find a place and the restaurant picker now set case AND accents aside (`foldText`, as the dish
   search already did). The picker also searched a `city` field places do not have; it reads
   `location` now.

**Verified.** `test_malta.js` (real functions): failed before (3), 11 pass after (Malta with and
without the postcode space, the shape refused outside Malta, Barcelona, Capri, Dallas and London
unchanged, accent-blind matches). Playwright at 375 px: typing "enchante" in Places finds only the
accented place.

### Show in $: menu prices in your own currency (2026-10-15, app 1.529.0, backend 0.145.0)

Chris: "we need to show a conversion of currency so we can see the menu and it's native currency,
but also to whatever you want to convert it to ... get that spot rate from somewhere cheap". By
card: **behind a switch**, rates from **Frankfurter** (free, no key, no account), which serves the
European Central Bank's daily **reference** rates for 30 currencies (about 16:00 CET on working
days). Not live market quotes and not a card's rate: the app says "about" (≈) and shows the date.

**Server (EXCHANGE RATES in main.py).** `GET /api/fx?base=XXX`, signed in. One EUR-based fetch from
`api.frankfurter.dev/v1/latest?base=EUR`, cached in memory 6 hours, made only when someone asks (no
background loop); any base is worked out as EUR->q / EUR->base. Source down: the last rates with
their date; nothing cached: 503. A currency without a reference rate: 404. **No user data goes to
Frankfurter**: the server asks for the public table with nothing about the user, so no privacy
policy change.

**App.** A "Show in $" chip under Show English, only when the menu's currency is known, has a rate,
and is not already yours. Off until turned on; remembered (`mc_menu_fx`). When on, each price gets
a quiet "≈ $14" under it, and a line shows "€1 = $1.12 on Oct 14  USD ▾"; the code opens the
phone's own picker for any of the 30 (`mc_home_ccy`; default = phone region, else USD). The app
fetches `base=EUR` once and keeps it 6 hours on the phone (`mc_fx`), so changing currency costs no
call. **Which currency the menu is in** (`menuCurrency`): what its prices SAY wins (€, £, CHF,
US$, R$...; a beach bar in Mexico pricing in US$ is not pesos), else the restaurant's country from
its address (COUNTRY_CODES gained AU, NZ, SG, HK, IN, IL, ZA, ID, MY, PH, RO, BG, LU, SK, SI, EE, LV,
LT, CY and UK variants). "$", "¥", "kr" and "C$" alone name nothing. Bulgaria is on the euro since
2026-01-01.

**The rule: a price converts only when it is clearly a price** (`fxPriceText`). One number converts.
Several convert only when EACH is sure: a currency mark beside it, cents, or a size word before it
(glass, bottle, calice, bottiglia, copa, verre, S/M/L...). Skipped: ranges (14-18), portions (1/2),
counts and sizes (6 pcs, 30cm, 0,5 l, x2, "for 2 people"), a mark naming another currency, a
decimal on a won/yen/forint/krona/rupiah menu ("4.5" means 4,500 won), anything under a quarter of
a euro ("45" on a rupiah menu means 45,000), and any line mixing sure and unsure numbers ("2019
€85"). Whole units from 10 up ("≈ $14"), cents below. **Found by the tests before release:** a
"€" between two numbers was claimed by both (a vintage converted), and a capital L for Large was
read as litres.

**Verified.** `test_fx_backend.py` (real section, fake source): failed before, 7 pass (cross rates,
one source call, 404, yesterday's rates when down, 503, no loop). `test_fx.js` (real helpers sliced
from index.html): failed before, 53 pass. `test_fx_ui.py` (Playwright, 375 px, stubbed `/api/fx`):
14 pass (chip only on the Italian menu, nothing fetched until on, rate line, ≈ $18 and ≈ $32,
the wine line size by size, S.Q. untouched, pounds with no new call, remembered, none on a Dallas
menu, off again). Live: `/health` 0.145.0, `/api/fx` 401 without sign in, Frankfurter returned 29
rates plus EUR dated 2026-10-14. **Not done:** the shared and published menu pages (PublishedMenu,
PublishedVisit) do not convert yet; the "paid" amount a visit records is still shown with "$".

### Nightly off-site backups to Cloudflare R2 (2026-10-14, backend 0.144.0)

Chris: "how can we be assured that our data is backed up so they don't lose their pictures and
visits". Before this: Supabase Pro's daily database backups (7 days) and NO copy of any photo, and
nothing outside Supabase. He chose Cloudflare R2 ("Go with cloudflare"), and set up the account
(signed in with GitHub), the free R2 plan ($0; card on file), bucket **menucaptain-backups**, and an
Account API token with **Object Read & Write on that bucket only**. Claude set R2_ACCOUNT_ID and
R2_BUCKET in Railway and placeholders for the two secrets; Chris replaced those himself.

**What runs (BACKUPS in main.py).** Once a night at 09:00 UTC (~4 am Dallas), and once ~2 minutes
after a deploy when the last good run is over 26 hours old:
- `db/<date>.json.gz`: every table the service role can read (from PostgREST's OpenAPI document, so
  new tables are included automatically) plus accounts (id, email, created). **`scan_jobs` is
  excluded** (the policy promises its text is gone within 7 days). The file is READ BACK and every
  table's row count compared; a mismatch is a failure. Kept 30 days.
- `photos/<path>`: new photos only. A photo deleted in the app is removed from R2 29 days after the
  run that first sees it missing, i.e. within 30 days of the deletion.
- `state.json`: last good run and which photos went missing when.
- S3 Signature V4 written with hmac/hashlib (no boto3), tested against AWS's two published examples.
- `/health` `"backup"`: "ok <date>", "failed <date>", "waiting for keys", "not run yet" or "off".
  Kill switch `BACKUP=off`.

**Privacy policy** (wording approved by Chris by card): Cloudflare under service providers, and a
Retention paragraph: nightly copy, kept 30 days, deleted things gone from backups within 30 days,
short-lived scan text never copied.

**First run, live, 2026-10-14 23:55 UTC:** ok; 33 tables, 1,157 rows, 21 accounts, 1.0 MB
compressed, 610 photos copied, 0 failed, 201 s. Keys confirmed present by length only (32 and 64).

**Verified.** `test_backup.py` against the real section: failed before; 17 checks pass (AWS example
signatures, placeholders mean waiting, list pagination, every table paged past 1,000, scan_jobs
excluded, all photos first night and only new ones after, deleted photo kept then removed, old
database copies pruned, a short read-back is a FAILED run, next-run time, no secret in logs).
**Still to do:** a restore drill: download one night's file and load it into a scratch database
to prove it restores, not just that it reads back. And a Cloudflare budget alert is optional.

### Signing out clears the collections copy too (2026-10-14, app 1.528.0)

Found while checking the privacy policy for the backups work: it says signing out clears what the
app keeps on the device, and 1.527.0's `dininglog_collections` (and its dirty flag) survived a sign
out (both sign-out paths, `signOutHard` and Settings' Sign out button, removed only CFG_KEY and
DATA_KEY). Both now remove them. The cache was already tagged with the user id, so another person
never SAW the old copy; this makes the policy literally true. **Rule:** a new localStorage key that
holds account data must be added to both sign-out paths.

### Collections: a trip, or any set of meals (2026-10-14, app 1.527.0, backend 0.143.0)

Chris: "We should allow people to build collections, say, based on a trip, for example, we are on
our honeymoon". By card: **collections with optional dates**, **sharing with friends in the first
version**, and **a new table**. Everything in `COLLECTIONS` in index.html.

- **Model.** `{id, name, start, end, cover, include, exclude, created_at, updated_at}`, visit IDS
  only. With dates, every visit in [start, end] belongs by itself (`end` empty = still travelling,
  today counts), minus `exclude`; `include` adds any visit by hand. `colSetMember` records an
  exclusion for a dated meal and an inclusion otherwise. So meals logged later on the trip join
  without anyone doing anything.
- **Storage.** Server: `collections` in the whole-collection endpoint, one row per person like
  `lists` (table `collections`, FK cascade, RLS, `sql/collections.sql`). App: `collections` state,
  loaded after lists. **Plus a copy on the phone** (`dininglog_collections`, tagged with the user id)
  so a trip abroad on a weak signal still shows them; a save that fails sets
  `dininglog_collections_dirty` = the user id and is PUT on the next open (before reading the
  server's copy) or on the browser's `online` event. The flag names whose changes wait, so another
  person signing in on the phone can never send someone else's collections over theirs.
- **Screens.** History: "Start a collection" line, then a strip of photo cards. Collection page
  (`CollectionView`): cover (tap: choose from its own photos), title, date line, "N meals · N places ·
  N cities", Share / Map / Add meals, Edit in the header (four buttons wrapped at 375 px), favorite
  places (rated 4+), dishes you loved (with Special marks), then day by day ("Saturday, October 10 ·
  Day 1") with each meal's photos, stars, dishes and "Leave out of this collection". Map reuses
  `MapView` with only the collection's places and its name as the title. Log / Edit visit: a
  "Collections" row (chips) when any exist, "Part of X by its dates. Tap to leave it out.";
  the choices ride `extras.collectionPicks` and are applied with the save (`applyCollectionPicks`).
- **Sharing.** `CollectionShareSheet` sends kind `collection` (server allows it, keys it by `cid` in
  the Sent list, replies accept it): per meal place, city, cuisine, date, stars, dishes with y/s
  marks, up to 3 photos (36 in all, signed 12 at a time by `signPhotoMap`), the cover, an optional
  note. NEVER notes, companions, money or dish notes (tested). Friend side: `PublishedCollection` in
  the inbox. Road not taken: a public link page for a collection.
- **Found in passing and fixed:** account deletion never removed saved check splits (no FK, not in
  the list): names and amounts left behind. 0.143.0 deletes `splits` and `collections` too.
- **Privacy policy**, wording approved by Chris by card: a "A collection" line under what travels,
  "or a special" on the visit line, the Sent-list paragraph names collections, "Your content" lists
  collections.

**Verified.** Server `test_collections_backend.py`: the old server refused the name (404); 10 checks
pass (empty for a new user, save and read back per person, one row per person, non-list and
oversize refused, share subject key, share and reply kinds, deletion list). Live: `/health` 0.143.0,
`/api/collection/collections` 401 without sign-in; table checked (RLS on, 0 policies, anon and
authenticated cannot read, service_role can write). App rules `test_collections.js` (sliced from
index.html): 21 checks (open-ended trip runs to today and gathers tomorrow's meal, end date closes
it, exclusion and re-inclusion, hand-picked, date order, date lines, day numbers, stats, payload
fields and marks, 3 photos a meal, cover, NEVER notes/companions/money, unticked photos sign
nothing, 36 cap, real signing 12 at a time). Screens `test_collections_ui.py` at 375 px against a
pretend server: 18 checks (start, create, saved without copying meals, day numbers, highlights,
special mark, leave out, add by hand, share payload and privacy, History strip, visit form row and
leaving out on save, offline save kept and marked, sent on next open, inbox lists and opens the
friend's view). **Not checked:** real photos (the test copy cannot load them), a real phone.

### The weekly update email, "From the Captain's Table" (2026-10-14, app 1.526.0, backend 0.140.0)

Chris: "Should we have a deal where we email users of any feature updates and bug fixes, perhaps
just a weekly update". By card: **"Yes, email everyone"** (with an unsubscribe link in each, over
asking people first). Then, through drafts: "do a graphic of the features" ahead of the details,
link it to "the full promo", add how to send suggestions, and "Everything we should do needs to be
elegant and beautiful because we have high end customers". Users are addressed as **Captain**; the
series is **From the Captain's Table** (card, same day).

**The rhythm (Chris, 2026-10-14): one issue a week, sent on Thursday** (draft ready Wednesday), "with
features bug fixes and other things that we change", drafted from that week's MenuCaptain Log, approved by Chris, previewed with his button,
sent with his tap. The first issue opens with a welcome to the Captain's Table and has the subject
"Welcome to the Captain's Table: ..."; later ones use "From the Captain's Table: ...".

**Built and removed the same day (server 0.141.0 to 0.142.0):** an automatic preview, the server
reading `news/` every 3 minutes and emailing Chris each new version itself. Chris had chosen
"automatic previews" on a card that did not say how; on hearing it, "No, that's ridiculous. You don't
need to check something every 3 minutes." Do not rebuild it. Name the mechanism on a card.

**Making an issue (on the PC).** `CG Apps\MenuCaptain\MenuCaptain Updates\`:
`<date>-whats-new.md` (Subject line + body, approved by Chris), `<date>-tiles.json` (graphic: kicker,
date, one lead feature, four more), `make_update.py <date>` renders `out/<date>.png` (1200 px, navy and
gold, Fraunces + Outfit via headless Chromium), `out/<date>-email.html` and `.txt` (with
`%%UNSUBSCRIBE_URL%%` and `%%POSTAL_ADDRESS%%` left for the server) and a preview picture.
`--publish` copies them to `dining-log-app/news/` and writes `news/latest.txt`; commit and push
separately. The email's graphic and button open **menucaptain.com/welcome.html**, the public promo,
refreshed the same day to the same standard. NEVER link the living promo brief: it is an internal
filming brief with don't-film notes about real people.

**Sending (owner only).** Settings → **Update email** (`UpdateEmailCard`, shown when `isOwner`):
opens on `news/latest.txt`; **Email me a preview**, **Who gets it?**, then **Send to N people** with a
confirm. Server `POST /api/admin/updates/send` {issue, mode preview|count|send, expect}:
- fetches the issue from `APP_URL/news/`, refuses one without both placeholders or a subject;
- preview goes to the owner's own account email, subject prefixed "[Preview] ";
- recipients = every auth user with an email, deduped, minus `update_email_optouts`; if that table
  cannot be read NOTHING is sent;
- send refuses when `UPDATES_POSTAL_ADDRESS` (Railway, set 2026-10-14 to the MilSpo Life LLC Dallas
  business address Chris gave) is unset, when `expect` differs from the count, or when the issue was
  already sent in this server run;
- each email: from `news@menucaptain.com`, reply-to `support@menucaptain.com`, its own signed
  unsubscribe link, `List-Unsubscribe` + `List-Unsubscribe-Post` (RFC 8058), 0.6 s apart (Resend's 2/s).
- **Unsubscribe:** `share.menucaptain.com/u/unsubscribe?u=&t=`. GET shows a confirm button only (mail
  scanners open links); POST unsubscribes (page button or a mail app's one-click), with Resubscribe.
  Token = HMAC of the user id, keyed off the service role key (road not taken: a dedicated secret,
  which needs a new Railway variable; rotating the service key breaks old links, the page then says
  to reply instead). New table `update_email_optouts` (user_id, created_at), `sql/update_email_optouts.sql`.
- **Gaps, on purpose:** "already sent" is remembered per server run only (the log is the record);
  no in-app Settings switch for the person yet (the email's link is the switch).
- **Privacy:** two lines added and live the same day, wording approved by Chris by card: "To send you
  an occasional email about what's new in MenuCaptain. Each one has a link to stop them, and stopping
  them doesn't affect emails about your account or things friends send you." (How we use your
  information) and "our occasional update emails" on the Resend line.

**Verified.** `test_news.py` runs the real server section against stand-ins (users, opt-outs, the
published issue, Resend): failed before, 23 checks pass (owner only, date-shaped issue, count dedupes,
preview to owner only, refusals with nothing sent: no address, count changed, opt-out list unreadable,
missing placeholder, already sent; each email's own link and headers; no email address in the log;
unsubscribe page changes nothing on GET, button, resubscribe, one-click, someone else's token).
Live: `/health` 0.140.0, the send answers 401 without sign-in, the unsubscribe page answers. Table
checked (RLS on, 0 policies, anon/authenticated cannot read, service_role can write). App card:
`test_updatecard.py` at 375 px against a pretend server, 6 checks (owner sees it, opens on the newest
issue, count shown, preview message, confirm then send with expect=21, call order). Issue online at
menucaptain.com/news/. **Not yet:** a real preview through the server (Chris's tap) and the real send.
**Tool notes:** the Railway and Resend connectors here cannot take object/array arguments; the Railway
CLI (`railway variable set ... --service --environment --project`) works.

### The name list stops blocking "What you had" (2026-10-14, app 1.525.0)

Chris, with a screenshot of Log a visit, the "Who was with you?" list open over "What you had":
"It won't let me put what I had until I add who I was with, and that list obfuscates the rest of it".

**Cause.** `PeopleTag` drew its suggestions `position:absolute` over the page AND put a full-screen
`position:fixed` layer behind them (zIndex 5) so that "a tap anywhere else closes the list". That layer
swallowed every tap: the first tap on "What you had" only closed the list, and the list itself covered
the dish box. Same family as the dish suggestions fixed in 1.522.0.

**Fix.** The list renders in the page under the box (pushes the rest down), the invisible layer is
gone, and the list closes when the box loses focus (`onBlur`, 180 ms grace). Rows and Done use
`onMouseDown preventDefault` so a tap on a name lands before the blur closes the list.

**Rule for the next dropdown:** no floating lists and no tap-catching layers in a form. In the flow,
close on blur. Two have now cost Chris a screenshot each.

**Verified.** `test_people.py` (headless Chromium at 375 px, made-up names) on the real app: the old
1.524.0 failed 3 checks and could not even tap the dish box ("subtree intercepts pointer events",
exactly the report); 1.525.0 passes all 6: the list opens on tap, is in the page, "What you had"
starts below it, no tap-catching layer, tapping the dish box closes the list and focuses it, tapping
a name still adds it. **Not checked:** a real iPhone.

### A Special switch on each dish (2026-10-14, app 1.524.0)

Chris, with a screenshot of Edit visit: "how do we handle specials? Is it just an item I add, or do I
mark it as a special? I'm not really sure what I see." Answer then: just an item you add; nothing
marked it. Offered by card: an automatic "Not on the menu" label (recommended), a switch, or leave
it. He chose **"Add a Special switch"**.

- Under each dish in Log a visit / Edit visit: **Mark as special** (star icon). Marked, it reads
  **Marked as special** in gold and the dish name gets a gold ✦ (`.special-star`). Tap again to
  unmark. Stored as `special: true` on the visit's dish; unmarking deletes the key (`toggleSpecial`).
- Shown as a gold " · Special" (`dishSpecialMark`, `.special-mark`) on the dish chips in History,
  on the place page's visit cards and on the place's recent-visit chips.
- A shared visit's plate carries `s:1` (`buildVisitPayload`); the friend's page shows "· Special".
  Older links simply have no mark.
- Help me order is told "it was a special, so it may not be offered today" (`dishHistory` keeps
  `special`, the prompt adds the bit).
- The hint under the dish box now ends "...then Mark as special if it was one." Guide updated in two
  places.
- **First design rejected on sight:** an uppercase gold "SPECIAL" pill beside the name. In the narrow
  name column it wrapped onto its own line and pushed the pencil down. Replaced by the ✦ before the
  name. Chris's standard for anything a customer sees (2026-10-14): "elegant and beautiful... first
  class and polished".
- **The road not taken:** labelling automatically any dish not on the place's menus. It can't tell
  tonight's special from a dish the scan missed or an off-menu request.

**Verified.** `test_special.js` runs the real `buildVisitPayload`, `visitSpecial` and `dishHistory`
sliced from index.html: failed 3 of 6 before, all 6 pass after (s:1 on the special only, verdicts
unchanged, history keeps the mark, the prompt line exists). Locally at phone width: marking the
Branzino showed the ✦ and "Marked as special"; Save stored `special: true` and History's chip read
"Branzino al sale · Special"; a shared visit with `s:1` in the inbox showed "· Special" in gold;
unmarking and saving removed the key and the mark. **Not checked:** a real phone.

### Menu scans finish without you (2026-10-14, app 1.523.0, backend 0.139.0)

Chris, after 1.522.0's "stay on the screen" warning: "Yes, we should do the bigger job of having the
scan run without having to stay on the page. That will be a much better experience and some sort of
notification that it's done and instructions to that point". By card he chose **"Email if I'm not
back in 2 min"**, which also approved the new table and the privacy sentence below.

**How it works.** A photo scan is now a job on the server (`SCAN JOBS` in main.py, table
`scan_jobs`, record in `sql/scan_jobs.sql`).
- `ScanMenuFlow.runOcr` sends the photos ONCE (`startScanJob`, `POST /api/scan-jobs`, body from
  `buildScanJobBody`: the same prompts as before; 2-8 photos go page by page with the one-request
  prompt along as `single_prompt`). The server answers at once with an id. The screen then says
  **"You don't have to wait here"** with **Done for now** and **Stop this scan**; the header button
  reads Close. Only the few seconds of SENDING still need the app open (the screen says so).
- The scan screen asks every 3 s (`getScanJob`), and at once when the app returns to the front. App
  asks for the waiting list (`listWaitingScanJobs`, `GET /api/scan-jobs`) on open, on every return,
  when the scan screen closes, and every 12 s while one is running. Bars at the top: "Reading the
  menu for X...", "Your menu for X is ready" with **Review** and ✕ (hides it until the next open; the
  scan is NOT thrown away), or "A menu scan didn't finish" with OK.
- **Review** opens the normal review screen (`resumeJob` prop) aimed at the place and menu it was
  started from (`meta`, checked to still exist). Save or Cancel then tells the server to drop its
  copy (`collectScanJob`, `POST /api/scan-jobs/{id}/collected`). Closing while it is still being
  read leaves it running.
- **The notice:** a finished scan the app has not looked at within 120 s (`SCAN_JOB_EMAIL_AFTER_S`)
  gets ONE email, "Your menu for X is ready", button "Review it" to `?open=scan&job=<id>`, plus a
  push where native is registered (`scan_ready`). The app marks a job seen when it fetches it or
  lists it, so no email goes while the app is open. No email for a failed scan.
- The `?open=scan&job=` link is handled with the other `?open=` links (parked through sign-in) and
  opens the job once data is loaded; a job already saved, cleared or expired says so.

**Decisions inside it.**
- **The page-by-page fallback moved to the server for jobs.** When the pages can't be trusted (a page
  failed twice, ran out of room, unreadable, or two languages), the server reads all photos as one
  request itself, because the photos are there and the phone may be closed. `_pages_unusable`
  mirrors `scanPagesToMenu` / `menuPagesDisagreeOnLanguage`; **keep the two in step.**
- **Counting:** a job is ONE usage record, fallback included, with every token of both readings in
  its cost. The phone-side fallback recorded two calls. The allowance is checked BEFORE the job is
  accepted (`enforce_ai_limits` in the POST), so "out of scans" is said on the scan screen, not in an
  email.
- **Privacy:** photos are never stored, only the model's text and the place name; the result is
  cleared on collect and every row is deleted by an hourly sweep before it is 7 days old
  (`SCAN_JOB_KEEP_S` is 7 days less 2 hours, so "at the latest" holds). privacy.html, AI features,
  effective October 14, 2026: "If you leave the app while a menu is being read, our server keeps what
  was read from it (the text, not your photos) until you open it, and deletes it after 7 days at the
  latest." (approved by Chris on the card).
- **The road not taken:** a queue or worker service. The job lives in the backend process, so a
  deploy or restart during a reading loses it; the row is marked "interrupted" when next asked about
  (running, not being read here, older than 15 min, `SCAN_JOB_STALE_S`) and the app says to scan
  again. Not worth a second service at a few scans a day. **Deploying while someone is scanning
  costs them that scan.**
- `SCAN_INFLIGHT_KEY` (1.522.0) now covers only what still needs the app open: sending photos
  (value `<time>:photos`, its own boot message) and the link / find-it paths, which still read on
  the phone.
- A server without jobs answers 404 and the app reads the menu on the phone as before.

**Verified.** Backend: `test_scanjobs.py` runs the real section against stand-ins (database, provider,
email, push): failed before the change, 39 checks pass after (pages done and kept without photos; one
usage record; email after the grace period with the escaped place name and the right link; no email
when the app looked; fallback with all photos in order; retry then fallback; kill switch; too-long and
provider failures; cancel drops the result; another person's job 404s; junk ids 404; waiting list;
restart rule; 7-day sweep; refusals create nothing; the scan-pages endpoint unchanged). Live after
deploy: `/health` 0.139.0, `/api/scan-jobs` 401 without sign-in. App, locally at phone width
against a stand-in server: a ready job shows its bar on open; Review opens the review screen locked
to Villa Test with the two pages merged; saving made the menu and cleared the server copy; a new
two-photo scan sent kind pages with one photo per page, the one-request prompt, the place and its id;
the waiting screen and Done for now; the "Reading..." bar turned to "ready" on its own; ✕ hid it
without clearing it; the email link opened the review and cleaned the address bar; Cancel on review
let it go; a failed job's bar and OK; a single photo sent kind single; Stop cleared it; a failure
while on screen showed the error; the photos-interrupted message and a gone link's message; no
script errors. **Not checked, needs Chris's phone:** a real scan read on the server, leaving the app
during it, the email arriving.

### Dish suggestions stop covering the page; a scan warns you to stay (2026-10-14, app 1.522.0)

Chris, with a screenshot of Log a visit while typing a dish: "This pop-up is covering the other text,
and also I noticed when it's scanning the menu and I'm waiting if I exit out and come back on my
iPhone it crashes, so maybe there should be a warning to stay on the screen".

**1. The suggestion list sits in the page.** In `VisitForm` the type-ahead list was a card with
`position:absolute` inside the input's row, floating over the "Had a special..." line and the Browse
the full menu button. It now renders after the row closes, in the normal flow, so it pushes what is
below it down while you type and disappears when the box is empty.

**2. Leaving the app mid-scan.** On an iPhone, switching apps or locking the phone during a scan can
make iOS suspend or reload the page; the scan is lost and the restart looks like a crash.
- `ScanMenuFlow`'s waiting screen ("Reading the menu") now carries a card: **Keep MenuCaptain open
  until it's done** / switching apps or locking the phone can stop the scan.
- `SCAN_INFLIGHT_KEY` (`mc_scan_inflight` in localStorage) is set while `step === "working"` and
  removed when the step changes or the screen closes. If it is still there when the app next opens
  (under 30 minutes old), App says once, in the 6-second bar with an OK: "The menu scan stopped when
  you left the app. Scan it again and keep MenuCaptain open until it's done." A log line is written.
- **The road not taken, then taken the same day (app 1.523.0, below):** let the backend finish a
  scan on its own and keep the result for the app to collect on return. It survives anything, but it is much larger. Note the
  server may already have done, and COUNTED, a scan whose result the phone never received.

**Verified.** In the real changed app, locally at phone width: typing "Gno" lists Gnocchi and the Add
row in the page, below the box, with the hint line and the Browse button below the list and nothing
covered; an empty box shows no list. A scan marked as interrupted a minute earlier produced the
message on the next open, cleared the marker, and OK closed it. The warning card on the scan screen
was checked in the source, not rendered (reaching that step needs a real scan). **Not checked:**
iOS actually stopping a scan, which only a phone can show.

### The Back button that hid behind the status bar (2026-10-13, app 1.521.0)

Chris, with a screenshot of a friend's shared menu opened from Sharing: "Still having trouble seeing
the back button on this screen and won't get there".

**Cause.** The page declares `viewport-fit=cover` and `apple-mobile-web-app-status-bar-style
black-translucent`, so in the installed app every page runs UNDER the clock and battery. The standard
header (`.ovhead`) allows for that with `env(safe-area-inset-top)` and is pinned. Six full-screen
views were built by hand as `position:fixed; inset:0; overflowY:auto` and did not use it:
- **Two had their own small "Back" button 12px from the top of the scrolling page** (the shared item
  in `ShareInbox`, and an opened group-order invitation). It sat behind the status bar and scrolled
  away. Both now use `.ovhead` with `BackBtn`, a title ("From <name>" / the restaurant) and `HomeBtn`.
- **Four group-order screens** kept their own controls but started 14px from the very top. Their top
  padding is now `calc(14px + env(safe-area-inset-top))`.

**Rule for the next full-screen view:** use `.overlay` / `.ovhead`, or at the least
`env(safe-area-inset-top)` on whatever is at the top. A desktop browser cannot show this bug: the
inset is 0 there.

**Verified.** In the real changed app, locally at phone width: the shared item opens with a header
reading "From Anna", with Back and Home; the header is at the top before and after scrolling the
page; the Back button is 40px, on top, and tapping it returns to Sharing. **Not checked, and cannot
be on this PC:** the status-bar overlap itself. It rests on `.ovhead` being the same header every
other screen uses. His phone is the test.

### Picks from a friend's menu go back as a reply in the app (2026-10-13, app 1.520.0)

Chris, on a menu a friend had sent him inside the app, first asked what the + beside each dish means,
then: "why can't I send my picks back in the app itself as a reply". By card he chose in-app first,
with text as a backup. No backend change: it reuses `POST /api/replies`.

- **What the + is.** `PublishedMenu` in menu mode (`k:"m"`, not a place recommendation): tap a dish to
  pick it, a note box opens, a tray at the bottom counts the picks. "Send my picks" could only open
  the phone's share sheet with a text, because the screen was built for a public link with no account
  behind it. The one line explaining + sat at the top and scrolled away.
- **Now, opened from Sharing with a known sender:** `ShareInbox` passes `onSendPicks` and `sendToName`.
  The tray's main button reads **Send to <name>** and posts ONE reply
  (`picksReplyText`: "My picks: Dish (note), Dish") on the same subject the reply box above writes
  to, then reloads replies, so the picks show there at once. **or send by text** stays underneath.
- **A public link** gets neither prop and keeps the single "Send my picks" button.
- **The 500-character cap.** The backend cuts a reply at `REPLY_BODY_MAX` mid-word and silently.
  `picksReplyText` ends a long list cleanly with "and N more" (`PICKS_REPLY_MAX = 500`; keep the two in
  step). One enormous note is cut with "..." and the others still counted.
- **Clarity:** the hint now reads "Tap + beside the dishes you'd like, then send your picks to
  <name>." and the + / tick carry "Pick this dish" / "Picked" for screen readers.
- Changing a pick or a note clears "Sent", so a changed list can be sent again.

**Verified.** `scratchpad/test_picks.js`, 18 checks on the real helper and source. Then the real
changed app opened locally at phone width with a stand-in menu from a stand-in friend: hint names
her; two picks and a note; the tray reads "Send to Anna / or send by text" and fits in 375px; the
request that left carried the right friend, subject and "My picks: Roasted duck (no beetroot),
Barbecued octopus"; the button read "Sent" and reset when a third dish was picked. The reply endpoint
itself was stood in for (the static test server cannot take a POST). **Not checked:** a real friend
receiving real picks, and a real phone.

### The backend's libraries are pinned; a visit holds 10 photos (2026-10-13, backend 0.138.1, app 1.519.0)

**1. Pinned libraries (backend 0.138.1).** Chris: "Lock the versions", after being told what the
0.138.0 deploy had shown (see "Found while deploying" below).
- `requirements.txt` now pins all **56** packages with `==`: the 10 that `main.py` asks for by name,
  then the 46 they pull in. The versions are exactly the "Successfully installed" line of the live
  0.138.0 build log, so nothing about what runs changed. The script that wrote the file read it back
  and asserted the 56 pins equal the 56 installed.
- `uvloop` carries `; sys_platform != "win32"` (it has no Windows build; an unmarked pin would break
  `pip install` on this PC).
- **To upgrade, on purpose:** change a version in that file, push, watch the build and `/health`, read
  the startup log. One library at a time. Never go back to `>=`.
- No dependency was ADDED. Two names in the pulled-in set were new to us and were checked on PyPI
  2026-10-13: `httpx2` and `httpcore2` 2.13.1, both BSD-3-Clause, maintained by Pydantic. The rest of
  the pulled-in set was not re-audited for licence here.
- A change to `requirements.txt` always forces a full rebuild (several minutes, not 30 seconds).

**2. Ten photos per visit (app 1.519.0).** Chris asked to consider 8 -> 10. `MAX_VISIT_PHOTOS = 10`.
It is the one number: the visit form, the card's quick Add photo, and the page a friend sees all read
it (6 uses, no hard-coded 8 anywhere). Cost of two more: photos are shrunk to 1200px on the long edge
at JPEG 0.82 before upload, so a full visit grows by roughly half a megabyte; uploads resume; nothing
on the backend counts photos per visit. Unrelated and unchanged: a visit several people joined holds
24 between them (`SHARED_VISIT_PHOTO_MAX`). A friend on an older app version sees the first 8.

**Verified.** Backend: see the deploy check recorded in the Log entry for this date. App: opened
locally on stand-in data: a visit with 8 photos reads "Photos (8 / 10)" and still offers to add; a
visit with 10 shows all 10 on its card. In the same session the 1.518.0 "Share this visit" button was
tapped for real and opened the visit share sheet. **Small wart seen, not changed:** "Add photo" on a
card whose visit is already full opens the picker first and only says it is full after you choose.

### A renamed menu keeps its shared copy; a section can be deleted (2026-10-13, app 1.518.0, backend 0.138.0)

**1. Renamed menus and the community library.** Chris shared a dessert menu, corrected its name, and
the app wanted it shared again: "it's basically the same menu, so try to figure out how to reconcile
that".

*Cause.* `community_menus` is unique on (place_id, LABEL, contributor_id), and the app decides "have I
shared this?" by comparing labels. A local rename therefore made the menu look unshared in three
places at once: the place page's share nudge, the Share sheet's pre-ticked list, and "Menus shared
here", where his own old-named copy appeared as pullable and labelled "From another diner". The only
existing tidy-up (`/prune`) runs AFTER a re-share, so it needed him to do the thing he was objecting to.

*Fix.* The label is the only thing that changed, so the CONTENTS identify the menu.
- Backend: `POST /api/community/menus/reconcile {place_id, menus:[{label, names}]}`. `_plan_reconcile`
  (pure): for each of the caller's copies whose label matches no menu the phone holds, score dish-name
  overlap (Jaccard, lower-cased, spaces collapsed) against each of the phone's menus. At
  `COMMUNITY_SAME_MENU` (0.8) or better, with one clear best match, the copy's label is MOVED to the
  new name. If the caller already has a copy under that name, the old one is dropped instead. Only
  rows with `contributor_id` = the caller are ever touched.
- App: `communityListReconciled(cfg, placeId, localMenus)` replaces the plain list call in the share
  nudge, `CommunityMenuPanel.load` and `ShareSheet`. It reads the library; only if one of YOUR copies
  is an orphan (`communityHasOrphan`) does it send `communityLocalSummary` and read again. Best effort:
  on failure the plain list comes back and share-again still works. The nudge effect's deps now
  include the labels, so a rename is picked up without reopening the page.
- A copy of yours that matches nothing (a menu you deleted) stays in the library, and the panel now
  says "You shared this. It is no longer among your menus." rather than calling it another diner's.

*Cautious on purpose.* Wrongly merging two menus would publish one under the other's name to everyone.
Below 0.8, or with two equal matches, nothing happens. *The road not taken:* a stable id per
contribution kept on the phone. Exact, but nothing already shared has one, so it could not have fixed
the copies that exist.

**2. Delete a section.** Chris: a section can be moved into a menu of its own, "but also there should
be just a delete option when I've done something accidentally redundant".
- `deleteMenuSection(list, menuId, idx)` (pure): null for a missing menu, a bad index, or a menu's
  ONLY section (that is deleting the menu, which has its own button).
- The section's split icon now opens "Move ... / Delete this section instead". Delete is a second tap
  with the item count and "This cannot be undone". Offered only when the menu has more than one
  section. Visits are untouched: a dish logged from the section stays on the visit by name.
- `onDeleteSection` is wired App -> MenuDetail -> MenuView, beside `onSplitMenu`.

**3. Share a visit from its card on the place page.** Chris sent a screenshot of "Visits here" on a
place page: "I can't share from here the visit". A visit could be shared from History, from inside
the visit, and (since 1.512.0) from the place's Share sheet, but not from the card where its photos
are. The card's button row now has **Share this visit**, which opens the same `VisitShareSheet`
(`setShareVisitObj(v)`, already wired in `RestaurantDetail`).

**Found while deploying, NOT fixed: the backend's libraries are not pinned.** `requirements.txt` uses
`>=` everywhere. Most deploys reuse a cached layer and take about 30 seconds. The 0.138.0 deploy
rebuilt from nothing: it took 9 minutes (17:26 to 17:35 UTC) and pulled the newest of everything
(starlette 1.8.0, pydantic 2.14.1, new `httpx2` / `httpcore2` packages, and so on). It started
cleanly and `/health` is fine, but any cold build can pick up a breaking release with no code change
on our side. Pinning to the versions now running (a lock file) would stop that.

**Verified.** Backend `scratchpad/test_reconcile.py`: 17 checks (someone else's copy with the same old
name is not touched; a copy at another place is not touched; half-different contents are not merged;
calling twice changes nothing). App `scratchpad/test_rename_delete.js`: 24 checks, including the real
`communityListReconciled` flow against stand-in network calls. Delete-section tapped through in the
real app locally: confirm, Keep it, then delete, and the saved data showed the section gone.
**Not checked:** the real rename case on his phone. It should resolve itself the next time he opens
that place: watch for `[COMMUNITY] reconciled user=... renamed=1` in the Railway log.

### The screen is "Sharing", and a Sent row counts friends instead of naming them (2026-10-13, app 1.517.0)

Chris, looking at the real Sent list on his phone the same day it shipped: he sends to everyone and
the friend list is growing, so show fewer names with all of them a tap away; and the screen is called
"Shared with you" but now runs both ways, so it is really "Sharing". No backend change.

- **Sent rows.** `sentToLine`: one or two friends are named; three or more read "to 10 friends".
  For one day (1.516.0) it named two and said "and 8 more": every row led with the same two names and
  told him nothing, and three names wrapped to a second line. Each row now has a `Chevron`, because
  nothing showed that a tap lists every name. Tapping still shows all the names and Remove.
- **The screen** (`ShareInbox`) is titled **Sharing**. Inside: **Replies**, **Shared with you** (what
  friends sent, now ALWAYS headed, with "Nothing waiting..." when empty) and **Sent**. Both ways in
  are relabelled: the You-tab entry and the + sheet item read "Sharing".
- **Left alone on purpose:** the Home banner ("3 things shared with you"), the picker's "in their
  Shared with you inbox", and the backend's push and email titles. Those are about what a friend
  SENT you, which is still the name of that section.
- Guide: the three places that told you to open "Shared with you" now say "Sharing".

**Verified.** `scratchpad/test_sent_strip.js` (27 checks now). The real changed app opened locally on
stand-in data: the screen reads Sharing / Shared with you / Sent, a send to ten reads "to 10 friends"
with an arrow, a tap lists all ten. At phone width (375) nothing runs past the edge. **Not checked:**
his phone.

### The Sent list, and the place page's photo strip put in order (2026-10-13, app 1.516.0, backend 0.137.1)

Chris asked on 10-11 and again on 10-13 where he can see what he has shared and with whom, and on
10-12 what the "Photos from your visits" strip is meant to be. Offered both; he said "Build and fix".
The Sent list was approved by card, the option naming the new table, the backend release and the
privacy sentence.

**THE SENT LIST**

*Why there was nothing.* A `shares` row is the friend's INBOX item and is deleted when they save or
dismiss it. A visit in History said "Sent to" with names, but each name dropped off as that friend
acted; a place said nothing; there was no list.

*New table `share_log`* (`sql/share_log.sql`, applied live 2026-10-13 as migration `share_log`): one
slim row per recipient, written at send time: `from_user_id`, `to_user_id`, `kind`, `title`,
`subject_key`, `created_at`. Both user columns cascade from `auth.users`, so account deletion needs no
extra step. RLS on, no policies, granted to `service_role`. Checked after applying: RLS on, 0
policies, anon and authenticated cannot read, the backend can write.
- **It holds no payload** (photos and contents are not kept twice) and **nothing about what the friend
  did with it.** A version showing saved / dismissed / not yet opened was on the card and was NOT
  chosen: it is a read receipt, in both directions.
- `subject_key` = a visit's shared-record id (`sv`, the id its "Sent to" line is keyed by) or a
  place's Google id. NULL for places sent before app 1.512.0, which carried no id; those list by title.
- **Seeded** from the 52 rows then in inboxes (29 visits, 23 places, 14 sends, one sender). Anything a
  friend had already saved or dismissed before 2026-10-13 is gone and is not in the list.

*Backend 0.137.0, then 0.137.1.*
- `POST /api/shares` also writes the log. **Best effort on purpose:** the items are already in the
  inboxes, so a log failure warns (`sent-log insert FAILED`) and the send still succeeds.
- `GET /api/shares/sent`: one entry per SEND. Rows from one send share one timestamp exactly (one
  statement), so (created_at, kind, title) is the key (`_group_sent`). Returns `ids`, `to` (names, not
  de-duplicated: two Annas are two people) and, from 0.137.1, `to_ids` so the app can show YOUR name
  for a friend. Declared before `GET /api/shares` and the `{share_id}` route.
- `POST /api/shares/sent/delete {ids}`: removes the caller's own entries only (scoped by
  `from_user_id` in the same statement). It removes the RECORD; the friend keeps what was sent.
- `/api/shares/activity` reads the log as well as the inbox rows, so a visit's "Sent to" line in
  History stops losing names.

*App 1.516.0.* `SentList` (its own component) at the bottom of the Shared with you screen, under a
"Sent" heading: title, kind, when (`replyWhen`), and `sentToLine` ("to Anna, Ben and 8 more"). Tap to
see every name and "Remove from this list". Shows 20, then "Show all N". On a backend with no list
(404/405) it hides itself. `sentNames` prefers `getConnName(id)` over the profile name.

*Privacy policy* (wording shown on the card): a paragraph under Sharing saying the record is kept, what
is in it and what is not, and that it can be removed and goes with either account. Effective 2026-10-13.

**THE PHOTO STRIP**

*What it was.* Every photo from every visit at the place, meal and per-dish, the first 12, in whatever
order the visits were stored, and a tap opened the viewer on that strip. Chris tapped it expecting his
most recent visit.
*What it is now.* `placeStripPhotos(visits, 12)` (pure): newest visit first (date, then `logged_at`), a
visit's meal photos then its dish photos, no repeats, each remembering its visit. `PhotoLightbox` takes
optional `captions` (parallel to `paths`, which must then have no blanks): under each photo, "From your
visit on <date>" and **Open this visit**, which closes the viewer and calls `onOpenVisit`.
*Not done:* making a tap go straight to the visit. It stays a gallery of the place.

**Verified.** Backend: `scratchpad/test_sent.py`, 24 checks on the real shares section against a
stand-in database (the log holds no payload; clearing an inbox keeps the name; another person's ids
remove nothing; a failing log does not fail a send). Live: `/health` reports 0.137.1 and both new
routes answer 401 without sign-in. App: `scratchpad/test_sent_strip.js`, 23 checks. Then the real
changed app opened locally, signed in on stand-in data: the Sent section listed three sends, a tap
showed all ten names; the strip started with the newest visit, the captions followed the visits, and
"Open this visit" on a June photo opened the June visit. **Confirmed on Chris's phone 2026-10-13 (his screenshot):** the Sent section
lists his earlier sends under Replies, newest first, with kind, date and names. One place sent to
ten on 10-11 shows eight: two friends had dealt with it before the seed, as expected. **Still not
checked:** a NEW send appearing, removing an entry, and the photo strip on his phone.

**Local testing, one more trick.** A path that is both an endpoint and a prefix (`/api/shares` and
`/api/shares/sent`) cannot be a file and a folder at once. Make it a folder holding `index.html` with
the JSON in it: the static server answers the folder with that file.

### The dish search on Log a visit stopped at 8 and read names only (2026-10-13, app 1.515.0)

Chris, at a place with three menus (45 + 122 + 27 = 194 items), could not find something he knew was
on one of them and asked whether "What you had" only searches the main menu. **It always searched
every menu at the place** (`menus[restId]`, all sections). What hid things was the matching. He was
given the three causes and said "Fix the search". No backend change.

**The three causes, all in `VisitForm`'s type-ahead:**
1. `.slice(0, 8)` on the matches, in menu order. A short word filled its 8 from whichever menu came
   first and gave no sign there were more.
2. Only the dish NAME was searched, so typing an ingredient found nothing.
3. Plain `toLowerCase().indexOf`, so "tiramisu" did not find "Tiramisù". (Least likely at his place:
   5 of the 194 names have accents. Aggregate query, 2026-10-12.)

**What it does now** (pure helpers above `dishIsDrink`): `foldText` (lower case, accents removed),
`searchDishes(query, pool, meta, exclude)`, `canonicalDish(typed, pool)`.
- Ranked: the name starts with it; a word in the name starts with it; somewhere in the name; every
  typed word in the name in any order; every typed word in the name OR the description. Ties keep menu
  order. A description match carries `why` (the description), shown under the name.
- All matches are listed, up to `DISH_SEARCH_SHOWN` (40), then "N more - keep typing to narrow it
  down". The list is taller (300px).
- Each row says which menu it is on when the place has more than one (`dishMeta`: name -> menu, desc;
  `menuGroups` items now carry `desc`).
- Typing a dish and pressing Add logs the MENU'S spelling when exactly one name here matches apart
  from case or accents ("tiramisu" -> "Tiramisù", keeping its section). Two candidates are left alone.

**The road not taken:** typo-tolerant (fuzzy) matching. A list that is hard to predict, and a wrong
near-match logged as what you ate is worse than no match.

**Known and accepted:** a description match is a plain substring, so "gin" also finds a drink whose
description says "ginger". It is ranked last and shows the description, so the reason is visible.

**Verified.** `scratchpad/test_dishsearch.js`: 29 checks on the real helpers, on a stand-in place
shaped like his (194 items, three menus), including three that reproduce the OLD behaviour. Then the
real changed app, opened locally signed in on a three-menu place: "gin" lists the cocktail with
"Cocktails" under it; "vodka" finds two drinks by description and shows why; "cocktail" draws 40 and
says "10 more"; "tiramisu" offers "Tiramisù" and Add logs it with the accent. **Not checked:** his real
place on his phone, and what he had actually typed (he was asked; the fix did not wait for it).

### "Select all" in the friend pickers (2026-10-12, app 1.514.0)

Chris: "The [share] friends inside the app function should allow for a select all function." The day
before he had sent one place to ten friends a tap at a time. No backend change.

- **Where:** the three places that list your friends with tick boxes: `ShareToConnectionButton` (send
  a place), `SendVisitToConnection` (send a visit) and `GroupInvitePicker` (invite friends to a group
  order). He asked for the share ones; the invite one got it too because it is the same list doing
  the same job.
- **What:** `PickAllRow`, one row at the top of the list, "Select all N friends". Ticked when everyone
  is ticked; a tap then clears everyone. Hidden with fewer than two friends. It is a row, not a
  button beside the title, so it reads and behaves like the rows under it.
- **`pickAllToggle(conns, pick)`** (pure) builds the new ticks from the LIST, never from the old
  ticks, so somebody who has left the list cannot stay ticked.
- **The button now says how many:** "Send to 10" / "Invite 10" when more than one is ticked
  (`pickCount`). Added because selecting everyone makes a slip expensive: each friend gets the item
  AND an email, and a send cannot be taken back.
- Guide: a short "Sending to several friends at once" paragraph under Sharing a visit.

**Verified.** `scratchpad/test_pickall.js`, 13 checks on the real helpers and source. Then the real
changed app, opened locally signed in with three stand-in friends (the 1.513.0 method below, plus a
static file at `<apiBase>/api/connections` returning `{connections:[...]}` so the picker has friends
to show): Select all ticks all three and the button reads "Send to 3"; unticking one gives "Send to 2"
and unticks the row; a tap when all are ticked clears them and disables Send. **Not checked:** an
actual send to several friends after the change, and a real phone.

### Specials and things not on the menu live on Log a visit only (2026-10-12, app 1.513.0)

Chris: "I don't think we should have specials or not on the menu on the place page. The more I think
about it, it's on the log a visit page, so we need to switch those up." By card he chose "Log a visit
only". He then asked what "the separate tips section" meant, was shown the card a friend sees, and
said "Go remove the box". No backend change.

**What went.**
- `OffMenuCard`, the "Not on the menu / specials" box under the menus on a place page (name, price,
  how to ask, a "Still true" date), and its `onSaveOffMenu` wiring in App. A comment stands where the
  component was.
- `off` in `buildPlacePayload` (a place shared by link or inside the app) and `sp.off` in
  `visitSpecial` (the "what makes this place special" part of a shared visit). `visitSpecialSummary`
  no longer counts specials, and a place whose only "special" content was old tips offers no tick box.

**What stayed, on purpose.**
- `restaurant.offmenu` is still READ in the visit form's dish pool, so names saved earlier are still
  offered when logging a visit. Nothing writes it. When this shipped the whole app held 2 tips, on 2
  places, from one person, out of 158 places (aggregate query, 2026-10-12). Those two can no longer be
  seen or removed anywhere; that was accepted over keeping a box for two rows.
- `PublishedMenu` still DRAWS `data.off` and `data.sp.off`, so shares sent before 1.513.0 show what
  they carried.
- Log a visit already took a typed dish (`Add "x"` / "Not on the menu - a special, perhaps"). New: a
  line under the dish box that says so BEFORE you type: "Had a special, or something not on the menu?
  Type it in and tap Add."

**The road not taken:** keep the friend's tips card, filled from what is typed while logging a visit.
Rejected: a special from months ago would read as a standing tip, and a friend would ask for it.

**Guide and policy.** HELP_DOC: "Off the menu" became a pointer to Logging a visit; the two "these live
on the place" and "Still true" paragraphs went; "Something not on the menu" now says where to type it
and that a friend sees it in what you had; both share descriptions dropped "off-menu tips".
`privacy.html`: the place line dropped "any off-menu tips you recorded"; effective 2026-10-12. The card
option Chris chose named the policy change; the exact sentence was shown to him at release.

**Verified.** `scratchpad/test_specials.js`: 14 checks on the real builders and source, and the same
test FAILED 9 of them against 1.512.0. Then the real changed app was opened locally, signed in on
stand-in data, with one old tip seeded on the place: the place page shows no box; Log a visit shows the
line; typing "Truf" offers the old tip; typing an unknown dish offers the Add row and puts it on the
visit. **Not checked:** a real phone, and a real share sent after the change.

**New, reusable: opening the app signed in, locally, with no account.** Until now anything behind
sign-in was "verified by reading". Make a COPY of `index.html` with `API_BASE_DEFAULT` and
`SUPABASE_URL` replaced by a dead local path (so it cannot reach the live systems), serve it from the
harness, and seed two `localStorage` keys on that origin before loading:
`dininglog_config` = `{apiBase, userId, email, accessToken, refreshToken:"", expiresAt}` with
`expiresAt` far ahead (so no token refresh is attempted), and `dininglog_data` =
`{restaurants:[...], menus:{<placeId>:[...]}, visits:[], locations:[], shas:{}, dirty:{}}`. The app
boots from that cache and shows "Backend GET failed (404)", which is expected. Remove both keys after.

**Found, not built (Chris asked the same day):** the "Photos from your visits" strip on a place page
is every photo from every visit there, meal and per-dish, first 12, NOT sorted by date, and a tap
opens the photo viewer on that strip, not a visit. He taps it expecting his most recent visit.

### Measured: translating the code in the browser costs about 0.8 s per fresh open (2026-10-12, no release)

Chris was told the one-file app is "monolithic" and asked whether to split it. Nothing was built. Two
things were established so the question does not have to be re-argued from scratch.

**The measurement.** Two copies of the committed `index.html` (1.512.0) were served locally with the
same probe (time until `#root` first has a child), signed out, warm cache, four loads each, alternating:
- **Today's page** (Babel in the browser, `data-presets="react"`): app drawn at **832-956 ms**.
- **The same code translated once beforehand, Babel's library tag removed:** **23-39 ms**.
- Same screen in both, no new console errors. Babel's own run on the 1.5 MB script took 690-860 ms in
  Node on the same PC, so nearly all of the gap is the translation itself.
- Also: the library is 588 KB compressed that a first visit no longer downloads, and the page shrinks
  from 431 KB to 381 KB compressed.
- **Limits:** the PC is a very fast desktop (i9-14900KF). No phone was measured; phones will be at
  least this slow and most will be slower. The cost is paid when the app starts fresh, not when it is
  brought back from the background. Only the signed-out screen was timed.
- To redo it: extract the `text/babel` block, `Babel.transform(code, {presets:["react"]})` with
  7.23.6, write it back as a plain `<script>`, drop the Babel `<script src>` tag, and compare.

**The shape, if this is ever reorganised: a modular monolith, never microservices.** One backend and
one web app, released as now, with the source kept in files by area.
- Backend: FastAPI routers, one area per release, no new tools. The tests that cut sections out of
  `main.py` by text search would need adjusting.
- Web app: needs a step before upload that joins the area files and translates them into the single
  `index.html` that is uploaded, so the live site and GitHub Pages do not change. Level 1 (files joined
  in order, same code as today) is low risk. Level 2 (strict boundaries between areas) is a long job.
- **CORRECTION, same day: this step already exists for the store app.** `build.js` in
  `menucaptain-native-build` has always translated the code ahead of time into `www/app.js` and
  dropped Babel ("no CDN, no runtime Babel"). So the store build does not pay the 0.8 s; only the
  WEBSITE does. Chris was first told the step would be new. Doing it for the website means reusing
  that script's steps 1-3, not inventing anything.
- A translate-only step, with no reorganising, gets the speed above by itself. `retainLines` would
  keep error line numbers matching the source. Its risk is a forgotten step uploading a stale file
  (the same family as the stale-stamp bug), so it needs a check before upload.
- Not before TestFlight is through. **PARKED.** Chris, 2026-10-12: "Put down for later consideration",
  not committed to. Nothing was built. Do not start it or re-propose it unprompted.

### A starter kit was cut for a separate companion app (2026-10-12, no release)

**Nothing in MenuCaptain changed.** A copy of the app, the backend and the database layout, taken at
app 1.512.0 / backend 0.136.0, was made for a separate app that has its own builder, its own repo and
its own accounts. It is a copy, not a fork: no shared history, no link back. Every address, project id,
key and user id was replaced by a placeholder and a scan of every file confirmed none is left. The
builder and the plain-English record are in the private notes (MenuCaptain Log, 2026-10-12).

**What that means for this session:**
- That project is not ours to edit and must never be pointed at MenuCaptain's systems. Nothing is
  pushed between the two. Ideas travel in words, through Chris, in both directions.
- When a bug is fixed here in code the copy also has (sign-in, connections, shares and replies, photo
  uploads, the AI relay and its meters, the table and function locks), tell Chris so it can be passed on.

**Facts the work established, useful here too:**
- The database has **30** public tables (an earlier count of 31 was wrong), 3 functions of ours, 4
  triggers, one private bucket. `sql/` in the backend repo has NO single file that rebuilds the
  layout; the kit's `00_base_schema.sql` is the only one. It was run in a throwaway Postgres 16 with
  stand-ins for the Supabase-only parts and matched the live layout table by table. It has not been
  run on a real Supabase project.
- Sign-up signs a new person straight in and sends no email, so it depends on "Confirm email" being
  OFF in Supabase. A new project has it on.
- The copy reads three things from settings that this backend still writes into the source:
  `OWNER_USER_IDS`, the CORS origin list, and the publish repo (`PUBLISH_REPO_OWNER` / `PUBLISH_REPO`
  / `PUBLISH_BASE_URL`, with publishing off unless all are set). Candidates to bring back here; NOT
  done, and not needed while there is one owner and one domain.
- Found, not changed: the guide's worked example of a shared page uses a real name and handle. Raised
  with Chris.

### A place sent to a friend is a recommendation with pictures; the Share sheet offers the visit (2026-10-11, app 1.512.0)

Chris sent a screenshot of what a friend received: "This is what a shared visit in the app looks like,
and I don't see any pictures". **It was a PLACE share.** Railway log: `[SHARE] ... sent place to 10` at
15:55Z; no `sent visit` since 10-10. He said "Both" to the two fixes.

**1. The in-app place share was a bare menu.** `ShareToConnectionButton.send` built
`buildMenuPayload` (k:"m") and sent it as kind "place", so the friend saw "A menu on MenuCaptain - tap
the dishes you'd like, then send your picks back", with no photo, rating or loved dishes. (I told Chris
the LINK version already showed photo and rating. Wrong: it showed loved dishes and off-menu tips only.)
- `buildPlaceSharePayload(restaurant, menuList, lovedNames, extras)` (pure) now builds k:"p":
  `buildPlacePayload` (place, combined menu, `loved`, `off`) + `a`, `gpid`, `lat`, `lng`, `rt` (your
  place rating, to the half star, from `placeRating`), `g` (Google's), `ph` (up to 6 signed URLs) or
  `hero`, `by`/`byn`. Private notes, About this place and `house_story` do NOT travel (asserted).
- **Photos:** `placeVisitPhotoPaths(visits, 6)` = newest visit first, no repeats; receipt and per-dish
  photos are never taken. A tick box in the picker, **on by default** (Chris's earlier choice for "what
  makes it special"), says how many. Unticked or none: the place's own saved photo as `hero`. **Never
  Google's photo** (its terms do not allow handing it on; see `signVisitHero`). Signed for 30 days, like
  a visit's. `fillGoogleRating` may spend one Places details call at send time, as the visit share does.
- `PublishedMenu` in place mode renders the rating row (stars with a half) and the photo grid with a
  tap-to-enlarge, the same layout as a shared visit. Link shares carry neither, so nothing renders.
- **Lost on purpose:** the in-app place share no longer offers "tap dishes and send your picks back".
  That flow still exists on a MENU link share and in group orders.

**2. The place's Share sheet never mentioned the visit.** `ShareSheet` takes `visits` and
`onShareVisit`; when there is a visit it shows **Share your visit** (most recent, with its date) under
**Send this place to a friend**, each with a line saying what it carries. `RestaurantDetail` renders
`VisitShareSheet` for it (`shareVisitObj`) and passes `onLinkVisitShared` -> App's `linkVisitToShared`.
The picker text ends "This sends the place, not a visit: what you had and who you were with stay with
you."

**Privacy policy** (wording approved by Chris by card): the place line now lists rating, loved dishes,
off-menu tips and the photos; effective date 2026-10-11.

**Verified:** 17 checks on the real payload builders (`scratchpad/test_placeshare.js`); the REAL
friend's page rendered in the preview from a real payload via `?menu=` (rating, Google score, three
photos, loved dishes, off-menu, menu; no sideways scroll). **NOT run:** the Share sheet and picker
(they need a signed-in app); verified by compile, the undefined-name check and reading.

**Still true:** there is no list of what you have sent (see the finding below).

### A photo that will not upload no longer freezes the visit form (2026-10-11, app 1.511.0)

Chris: on a bad connection the photos stop, a better connection never resumes them, "you gotta cancel
out and restart". He then pointed at FitnessCaptain's fix of the same day and said "fix it".

**Cause.** In the visit `onSave` (App), a failed `uploadPhotoBatch` did `flash(...); return;`. A normal
return reads as success to `VisitForm.save`: its `catch` never ran, `saving` stayed true, and the form
showed "Uploading photo 2 of 5. Keep this screen open." for ever with nothing behind it. Cancel was the
only exit and lost the entry. There was also no retry of any kind, and every Save minted NEW ids.

**Fix, on FitnessCaptain's pattern (its gym scan, v0.153.4: retry transport failures only, twice, after
2 s and 5 s, and say so):**
- `ghPutBinaryFile` marks a network failure or timeout with `err.transport = true`. A refusal from
  the server (any HTTP status) is not marked and is never retried.
- `putPhotoWithRetry` retries a transport failure after `PHOTO_RETRY_WAITS_MS = [2000, 5000]`, telling
  the screen "The connection dropped - trying again (2 of 3)". If `navigator.onLine === false` it calls
  `waitForOnline(PHOTO_OFFLINE_WAIT_MS)` (3 minutes), shows "No connection - waiting for it to come
  back", then pauses 1.5 s (the `online` event fires before requests work) and retries.
- `uploadPhotosResumable(cfg, uploads, shas, onProgress)` is the batch loop, now a top-level function
  so it can be tested; `App.uploadPhotoBatch` calls it. `onProgress(n, total, note)` gained the note.
  `_photosUploaded` (a Set of paths, this session) makes a second Save send only what is missing.
- **Stable names**, without which "skip what already uploaded" could not work: `stablePhotoId(blob,
  prefix)` (a WeakMap) gives each pending photo one id for its life, and `newVisitIdRef` gives a NEW
  visit one id for the life of the form. Both used to be minted inside `save()`, so every attempt
  re-sent everything to new paths and left the earlier copies stranded in storage.
- The visit `onSave` now **throws** on a failed upload; `VisitForm`'s catch clears `saving`, shows why
  under the header (`saveWhy`), and scrolls to it. `saveNote` carries the retry wording to the
  "Uploading photo 2 of 5." line.

**Where MenuCaptain differs from the sibling, on purpose:** it uploads photos one at a time, so it
retries only the photo that dropped; and a retry cannot double-spend, because putting a photo again
overwrites the same file (FitnessCaptain's retried scan can run twice). Photo quality was NOT lowered:
FitnessCaptain's shots are only read by the model, these are keepsakes.

**Covers every photo save**, since all go through `uploadPhotoBatch`: place photo, menu thumbnails,
adding photos to a visit. Their own failure handling was already non-sticking (a toast).

**Verified:** 19 checks on the real functions cut out of `index.html`, against a pretend network
(`scratchpad/test_uploadfix.js`): drop twice then succeed, drop three times and give up, second Save
skips what went up, a 413 is not retried, offline then back, the offline limit, stable ids.
**NOT run: the form itself.** The unlock path (`onSave` throws -> `VisitForm` catch) was verified by
reading. First real weak-signal save should confirm the Save button comes back.

**Road not taken (offered, not chosen):** save the visit first and upload photos in the background,
so the screen need not stay open. It needs photos kept on the phone across a reload and a queue.

**Tool note:** `verify_names.js` flagged the first `new WeakMap()` as an undefined name. It now ignores
the ECMAScript standard built-ins (a fixed list of the language's own names, not an app allow-list).
Browser objects are deliberately still checked.

### A menu with several photos is read with its pages at the same time (2026-10-11, app 1.510.0, backend 0.135.0)

Chris asked what "side by side" meant, liked it, and said "build it". Before: `digitizeMenu` put every
photo in ONE relay request, the model read them in turn, and the wait was the sum (about 135 output
tokens a second). Now, for 2 to 8 photos:

- **App:** `digitizeMenuByPage` sends one `{messages}` per photo to `POST /api/ai/scan-pages`, each with
  the one-page prompt (`menuScanPrompt(true)`: "this is ONE PAGE", report `lang`, and put dishes that
  carry on the previous page's section into a FIRST section named `""`). `mergeMenuPages` folds the
  pages in photo order: the empty-named first section joins the previous page's last section;
  same-named sections anywhere become one (case-insensitive); a dish read twice (overlapping photos,
  same name and same price via `menuPageItemKey`, so "8" = "8,00") is kept once and the fuller
  description wins; same name at a different price stays two dishes. `finishDigitizedMenu` (the old
  tail of `digitizeMenu`, now shared) normalizes both paths to the same shape.
- **Server:** `ai_scan_pages` fans out with `asyncio.gather`, 4 at a time (`_SCAN_PAGES_PARALLEL`), max
  8 pages. **One `enforce_ai_limits` and one `record_usage` for the whole scan**, so it costs ONE call.
  That is why it is a server endpoint and not N relay calls from the phone: the allowance counts
  calls (Chris's 2026-09-22 choice, recorded at `MENU_TEXT_ONE_PASS`). A failed page is retried once
  alone after the gather (parallel bursts are what trip a rate limit); still failing, it returns
  `{"error"}` for that page. `_ai_call_failsafe` now holds the provider call + both fail-safes for the
  relay and scan-pages alike. Log: `[AI] scan-pages done user=.. pages=.. ok=.. retried=.. secs=..
  slowest=.. in=.. out=..`. **Switch off from Railway: `AI_SCAN_PAGES=off`** (404; the app falls back).
- **Falls back to the old single request, never worse than before,** when: the server says no (404,
  older server), a page errored or hit `max_tokens`, fewer pages came back than were sent, or
  **the pages are in different languages** (`menuPagesDisagreeOnLanguage`). That last one is the
  design constraint: only a request that sees every page can pair "the same dish in two languages";
  read apart, every dish would be listed twice. **Cost of a fallback: the pages were already read, so
  that scan counts as two calls.** Logged as `[VISION] Pages not read separately (<why>)`.
- One photo, or more than 8, is read exactly as before.

**Verified:** server, 17 checks on the real endpoint with timed stand-in calls (4 x 0.3 s took 0.31 s,
never more than 4 in flight, one gate, one usage record, retry, kill switch); app, 22 checks on the
real functions cut out of `index.html` by Babel source positions (`scratchpad/test_scanpages_front.js`).
Live endpoint answers 401 with no sign-in. **NOT verified: a real multi-photo scan.** Unknowns only a
real one can answer: whether the model reliably uses the empty section name for a continued section
(if it invents a heading, the merge leaves a stray section), whether parallel calls hit the
provider's rate limit on this account, and whether per-page reading is as accurate as whole-menu
reading. Read the first real merged menu against the paper.

**Diagnosed the same day, NOT fixed (Chris dismissed the card; do not build without his word):**
- ~~Photo upload leaves the visit form stuck.~~ **FIXED in 1.511.0, see the section above.**
- **There is no record of what you sent.** `GET /api/shares` lists only what was sent TO you, and a
  `shares` row is deleted when the friend saves or dismisses it. The History line "Sent to <name>"
  (`/api/shares/activity`) reads those same rows, so a name DISAPPEARS once that friend deals with the
  item; places, menus and lists show nothing at all. A real "Sent" list needs a durable record written
  at send time (a small table, or rows marked handled instead of deleted): a live database change.

### Sonnet 5.5 for every AI task; scans skip up-front thinking; calls are timed (2026-10-11, backend 0.134.0)

Chris: menu scans "take a while", should we move to a newer model? **Decision (his): Sonnet 5.5 across
the board.** He was offered scans-first and "stay on Sonnet 5, fix thinking only" (my recommendation
once the price turned out equal) and chose the full move.

**Measured before changing anything** (Railway log, 22 scans, 10-08 to 10-11, by pairing `POST relay`
with the next `relay success` for the same user): median about 56 s, 9 of 22 over 80 s, longest 210 s.
With the `[COST]` line's token counts: **about 135 output tokens a second**, and a scan is 4,000 to
17,000 output tokens. Scan time is output size divided by that rate.

**What was configured before: nothing.** The relay sent model, max_tokens, messages and system only.
So every task ran on the provider default, which on Sonnet 5 AND 5.5 is **adaptive thinking at high
effort** (Anthropic's thinking table, read 2026-10-11): the model reasons privately first when it judges
that useful, billed as output. Evidence it was happening on scans: the SAME photo scanned twice cost
17,234 output tokens then 11,904; another pair 11,296 then 9,088. Strong evidence, not proof.

**What changed:**
- `AI_MODELS_BUILTIN`: all 8 tasks -> `claude-sonnet-5-5`. Alias `sonnet` -> 5.5; new alias `sonnet-5`.
  **Revert with no deploy: `AI_MODEL_DEFAULT=sonnet-5` in Railway** (or `AI_MODEL_OCR_MENU=...` for one).
- `_thinking_kwargs(task, model)`: for `AI_TRANSCRIBE_TASKS` (ocr_menu, ocr_receipt, translate_menu)
  it sends the setting that stops up-front thinking. **Each model spells it differently and rejects
  the others with a 400:** Sonnet 5.5 = `{"type":"between_tools"}` ("disabled" is a 400); Sonnet 5,
  Opus 5, Sonnet 4.6 = `{"type":"disabled"}`; Opus 5.5 cannot turn it off, so nothing is sent; any
  other model gets nothing. Judgement tasks (help_me_order, explain_menu, estimates, place_about) are
  unchanged. Effort is left at the default everywhere. Switch back: `AI_TRANSCRIBE_THINKING=on`.
- **Fail-safe in the relay**, because neither setting could be tried against the real provider before
  release (the key is only in Railway): a 400 while a thinking setting was sent retries once without
  it; a 404 on the model falls back to `claude-sonnet-5`. Both log `[AI] ... refused` / `not found` as
  errors. Grep for those after the first real scans.
- Relay success line: `[AI] relay success user=.. task=.. model=.. secs=.. in=.. out=.. stop_reason=..`.
- **Cost table corrected.** `AI_PRICES["claude-sonnet-5"]` said $3/$15; the real price is $2/$10 (the
  rise planned for 2026-09-01 was cancelled, per the pricing page). Recorded cost ran 50% HIGH for six
  weeks (a scan logged 19-28 cents, really 13-18). 5.5 added at $2/$10. `_price_for` now takes the
  LONGEST matching prefix, since `claude-sonnet-5-5` also starts with `claude-sonnet-5`.

**FIRST REAL CALLS, 2026-10-11 evening (Railway log, filter `secs=`):** both new settings were
accepted by the provider: no `refused` and no `not found` line, so neither fail-safe fired. One real
menu scan: `task=ocr_menu secs=24.3 in=15608 out=5198` = **214 output tokens a second, against about
135 on Sonnet 5**, and a far smaller answer than the 10,000-17,000 tokens scans were costing (no
thinking tokens). Chris, the same evening: "scanning has gotten a lot faster". Other tasks:
help_me_order 4.0 s, estimate_photo 2.3-4.0 s, all `end_turn`. One scan is one data point; quality was
judged by Chris using it, not checked against paper. That scan went through the relay (one request),
so **scan-pages has still not run for real**.

**Verified before release:** 26 checks on the real sections with a stand-in provider (`scratchpad/test_sonnet55.py`);
live log shows `models in force: ['claude-sonnet-5-5']` and `up-front thinking on scans/translations:
off`. **(At release:) NOT verified: a real AI call on 5.5.** Nothing has run on it yet; the first scan is the test.
Compare its `secs` and `out` with the baseline above, and read the menu it produced for missed dishes
or wrong prices before calling it better. If quality drops, revert first, investigate second.

**Found on the way, not fixed:**
- **Thinking counts toward `max_tokens`.** Help me order asks for 700 and group help for 400, with
  thinking on. One Help me order call on 10-10 20:00Z stopped at exactly 700 (`stop_reason=max_tokens`),
  so an answer was cut off. 5.5's effort levels are recalibrated and may think more. Watch the new
  success line for `stop_reason=max_tokens`; the fix is headroom on those calls or a lower effort.
- **Bigger speed levers than the model:** every photo goes in ONE request and the phone waits for the
  whole answer (no progress shown); and the digitizer's JSON repeats empty keys on every dish
  (`notes`, `calories`, `tags`). Reading pages in parallel, showing dishes as they arrive, or a leaner
  output shape would each cut the wait more than a model swap. Not built; propose before building.
- The app's advisory `VISION_MODEL` constant in `index.html` still says `claude-sonnet-4-6`. Harmless:
  the server routes by task and ignores it.

### Firecrawl credits: who is spending them is UNKNOWN; the balance is now read every 15 minutes (2026-10-11, backend 0.133.0)

The portfolio overview session asked whether this session's testing had spent Firecrawl credits: the
balance fell from 141 to 95 between two of this session's deploys on 10-11 (01:42Z and 11:21Z) with
no menu-from-link call on the live server. **Measured answer: not this session, not this server.**

- This session's transcript: 4,635 tool calls, none a Firecrawl connector call, ever. It never runs the
  backend locally and never reads the key; tests use stand-ins. In the 10-11 window, 111 tool calls,
  none able to reach Firecrawl. On 10-07 it made no tool call between 01:05:39Z and 02:46:59Z, so it was
  idle during the 02:02Z-02:07Z burn Firecrawl emailed about.
- Railway deploy log, 10-11 01:30Z-11:30Z, filter `MENU` (case-insensitive: WEBMENU, FINDMENU, MENUPIC):
  no scrape line. Four balance checks at cost 0.
- **The "tied to deploys" pattern was a sampling artefact.** The balance was read only at startup, 60s
  later and every 12 hours after startup, and each deploy restarts that clock, so a drop could only
  surface at the next deploy.
- **Search blind spot:** `_firecrawl_screenshot` logs under `[MENUPIC]` and its success line does not
  contain the word "firecrawl". Filter `MENU`, not `WEBMENU`, to see every scrape path.

**SUPERSEDED the same evening (backend 0.136.0): back to every 12 hours.** Chris: "you don't have to
check fire crawl every 15 minutes. That seems excessive." The spender had been found by then. Each
12-hour reading logs one line (the change, or "unchanged"). To time a drain again, set
`FIRECRAWL_CHECK_MINUTES` in Railway for a while (floor 5; a typo falls back to 12 h); no code change.

**Change (as first built, 0.133.0):** `_fc_credit_loop` polled every 15 minutes (`_FC_CHECK_EVERY_S`), silently unless the
number changes: `[FIRECRAWL] credits changed A -> B (-N) within the last 15 min` (a warning), plus one
"unchanged" line every 12 hours (`_FC_HEARTBEAT_S`). Cost is 0 credits, measured at every startup; a
nonzero cost still backs off to daily. 10 checks on the real section with a scripted balance series
(`scratchpad/test_fc_watch.py`). **Not yet seen live:** a change line (needs a real drop).

**SOLVED later on 2026-10-11 (reported by the portfolio overview session from Firecrawl's own activity
log; not re-read by this session):** the spender was Chris's own research through the Firecrawl
connector in claude.ai and phone chats, on the same Firecrawl account as MenuCaptain's key. 905 used:
connector 865 (one research run = 725), ChatGPT/Codex 36, **MenuCaptain's own API use 4**.

**Decisions, all Chris, 2026-10-11, in this session:**
- **No second Firecrawl account and no new key** ("I don't wanna mess around with A new API"). The
  overview session had recorded "separate accounts"; he reversed it here. MenuCaptain stays on the one
  shared account with the key already in Railway. Nothing changed on the server.
- **The connector stays on, and Claude asks before every use** ("I can use fire crawl It absolutely
  needs it, but it should ask"). For this session that replaces the old standing rule "never use the
  Firecrawl connector": it may be used when a page cannot be read any other way, after a card with a
  credit estimate. Built-in WebSearch/WebFetch still come first.
- Looked up for the account question and still true: Firecrawl's terms (updated 2026-10-07) are silent
  on second accounts; Hobby is 5,000 credits for $19/month or $190/year (pricing page, 2026-10-11).

**What that means for the app:** the 1,000 monthly credits remain shared with Chris's research. 95 were
left at 13:31Z on 10-11; the period ends 2026-10-25 19:35 UTC. At 0, menu import from a link stops
working on sites that block a plain fetch (camera scans are unaffected). The 15-minute watch is the
early warning: `/health` shows `menu_link_credits` low/out, and the log times every change.

### Replies: on the place page, a way in after saving first, and email links (2026-10-11, app 1.509.0, backend 0.132.0)

Chris asked for the first two known gaps of replies to be closed together, and reported an email link.

**1. A way in after saving first.** Saving a share deletes the inbox item, and the reply box lived on
it, so a friend who saved before saying anything was stuck. `ShareInbox.clearOpened` (every save path,
including "I was there") now calls `onKeepDoor(replyDoorFor(share))` BEFORE the delete. A **door** =
`{uid, name, kind, key, title, place, city, at}`: who shared it, the conversation's subject, and the
place's name/city slugs. App's `keepReplyDoor` stores doors in **`meta.reply_doors`** (one per person per
subject, newest first, cap 200) through `saveMeta`, so they sync with the account like `conn_names`.
**Dismiss leaves no door** (dismissing means "not for me"). Shares saved before 1.509.0 have no door.
Road not taken: stamping `shared_from` onto the saved restaurant record. The save code writes
restaurants in five branches across two components (new, existing match, want-to-try, log-my-visit,
PublishedMenu), each straight to the server; one hook in the inbox was far less to get wrong.

**2. Replies on the place page.** `RestaurantDetail` shows, under the cuisine line, every conversation
about this place: for the SHARER by exact subject key (`replyKeysForPlace`: `place:<where>`,
`menu:<where>`, `menu:<where>:<label>` for each menu, where = name slug + city slug, the same recipe
`replySubject` uses on the friend's phone), and for the FRIEND by door (`replyDoorsForPlace`: same name,
same city unless either side has none). A door with no conversation yet renders `ReplyStarter`
("<name> shared this with you - Reply"), which opens `ReplySheet` with `start` (reaction chips on).
A door also covers a place saved from a friend's VISIT ("Want to try"): its subject stays the visit.
History does the same for a joined visit (door key `visit:<sv>`). Both hold the open conversation as
`{uid, key}` (person + subject), not a thread id, so it can open before anything is said.
**Limit:** if the sharer renames the place or changes its city after sharing, their place page no
longer finds the conversation (it is still under Replies). Keys are built from current name + city.

**3. Email links (backend 0.132.0).** Chris tapped the button in an "accepted your friend request" email
and met a bare sign-in page. **On iPhone a web link cannot open a home-screen web app**; the browser has
its own storage and sign-in. That only ends with the store build (universal links). The fixable part:
the three friend-request emails and the share email linked to bare `APP_URL`, so the sign-in page gave
no explanation and left the reader on Home. They now use `?open=connections` / `?open=shares`, which
the app already handles (`arrivedFor` card: "this opened in your browser, sign in once", then straight
to the screen). Still bare: the group-order "placed" email (no `?open=` destination for an order).

**Verified in the preview** with the real components and the real place-page block sliced out of
`RestaurantDetail`: sharer sees only this place's conversation (another place's is not shown); a door
shows one starter (a door for another place is not shown); the starter opens an empty sheet with
chips; the first reply uses the door's subject key and the starter becomes a preview line; a place
saved from a visit replies under `visit:<sv>`; saving in the real ShareInbox hands over a correct
door and Dismiss hands over none. `verify_names.js` clean. **NOT verified:** App's `keepReplyDoor` /
`saveMeta` write and the History starter (wiring only, not run signed-in); two real accounts; the
real emails.

### Replies between friends, attached to what was shared (2026-10-10, app 1.508.0, backend 0.131.0)

Chris asked whether the app had messaging with friends. It did not. Offered: replies on a shared item,
reactions only, full chat, or nothing. **He chose replies on a shared item.** Full chat was the road not
taken: phone notifications are off, so loose messages would sit unseen, and it raises more store
questions. A conversation here is always two friends + one SUBJECT (a visit, place, menu or list).

**The finding that shaped it:** a `shares` row is an inbox item. `ShareInbox.clearOpened` and Dismiss
DELETE it. A reply hung on that row would vanish the moment the friend saved the thing. So replies have
their own table and name their subject by a key the app builds (`replySubject`): `visit:<shared visit
id>`, `place:<name slug>:<city slug>`, `menu:...`, `list:<title slug>`, plus a title snapshot.

- **Table `share_replies`** (`sql/share_replies.sql`), applied live 2026-10-10 with Chris's yes and
  verified: RLS on, 0 policies, anon/authenticated no access, service_role full. `thread` =
  `<lower uid>|<higher uid>|<subject_key>`, built by the backend only. Both user columns cascade from
  `auth.users`, so account deletion removes them.
- **Backend:** `POST /api/replies`, `GET /api/replies` (all the caller's threads + unread count),
  `POST /api/replies/read`, `POST /api/replies/delete`. Friends only = accepted connection and no block
  either way (`_reply_friends`); both refusals are the same 403 so a block is never revealed. Reading is
  filtered the same way, so unfriending or blocking HIDES a thread without deleting evidence. Delete is
  two deletes pinned to the caller as sender / recipient; either person removes it for both (same rule
  as a share). Body max 500. `reply` is a new report kind: only the recipient can report, and the report
  note carries the words (`[reply said] ...`) because a thread can be deleted before anyone looks.
- **Email (Chris's choice): first unread only.** A reply emails the other person only when they have
  nothing unread in that thread; checked BEFORE the insert; a failed check sends nothing. Push is called
  too but is inert (no `device_tokens` table).
- **App:** `ReplyThread` (messages, reaction chips when `canReact`, input, per-message report) is used
  in three places: a card at the top of the page opened from Shared with you (`tail={3}` folds older
  replies so the thread never buries the thing shared); a **Replies** section at the top of Shared with
  you (opens full-screen, swipe or button to delete); and `ReplyPreviews` + `ReplySheet` on a visit in
  History for the sharer (matched by `visit:<v.sv>`). App holds `replies {threads, unread}`, refreshed
  with `refreshShares`; a Home banner shows when unread changes; the app-icon badge counts it.
  Reactions: Want to go / Looks great / Been there. Only the person it was shared WITH gets the chips.

**Verified:** 31 checks on the real backend section against an in-memory database
(`scratchpad/test_replies.py`: friends only, block hides both ways, third person sees nothing, one
email per unread stretch, escaping, report, delete). The real components rendered in the preview with a
fake server: react, send by Enter, read-marking, refusal message, report sheet, delete, a new thread on
a place. Live endpoints answer 401 without a sign-in. **NOT verified: two real accounts end to end, and
the real email.** First real use should check both.

**Known gaps, on purpose for v1:** ~~a friend who saved a share WITHOUT replying first has no place to
start a conversation later; the sharer of a place sees replies only under Replies~~ **both closed in
1.509.0, see the section above.** Still open: no per-message delete.

**Privacy policy updated in the same release, wording approved by Chris:** replies added; the
shared-visit description corrected (it DOES carry the star rating and dish names); in-app account
deletion described as it is; effective date 2026-10-10. **Store privacy answers:** typed messages
between users are a new content type ("other user content" / messages). Re-check the App Store and
Play data-safety answers before submitting.

**New tool: `menucaptain-native-build/verify_names.js`.** Fails when the working `index.html` uses a
name it never defines that the last commit did not (a typo, or a function moved while still called).
The compile check cannot see those. Run it after `verify_compile.js`, before committing.

### Sign-up: one email box, a two-way switch, and no talk of a confirmation email (2026-10-10, 1.507.0)

Chris watched somebody sign up and it confused them: Create account was hard to find, the screen
seemed to ask them to check their email, and nothing said the account was theirs once they finished.
Re-checked first: `/auth/v1/settings` still reports `mailer_autoconfirm: true`, so no email is sent.

- **Sign in / Create account is a two-way switch** (`.auth-switch`) above the Email field, hidden only
  in the forgot-password view. Create account used to be a text link under a Sign in form. The chosen
  side is outlined, not filled, so the one filled button on the screen stays the action.
- **The second "Confirm email" box is gone** (`email2` state removed). Chris asked to pre-fill it; a
  pre-filled box only copies the first and checks nothing, and its label read as "go and confirm by
  email". He chose one box plus the read-back card. The typo guard is now `emailDomainSuggestion` and
  the read-back card only. The card's button is "Yes, create my account" and its text says the account
  is created on the spot and nothing is emailed. A line above the Create account button says the same,
  because the header has scrolled away by then on a phone.
- **Three false messages removed**, with `pendingConfirmEmail` and the dimmed Sign in button: the
  rate-limit reply ("we just sent your confirmation email"), the no-session fallback ("we sent a
  confirmation link") and the sign-in error ("your email may not be confirmed yet"). Wrong sign-in
  now says "That email and password don't match. Check both, or tap Forgot password."
- **No session back from sign-up** now signs in directly with the credentials just entered; only if
  that fails does it switch to sign-in with "Your account is created. Sign in below...".

**This reverses the 2026-09-28 note below** that the "confirmation is on" branch was left in place on
purpose. Chris asked for it gone. **Tripwire: if email confirmation is ever turned back on in
Supabase, restore a "check your email" path in `signUp` FIRST**, or new people will be told to sign in
to an account that cannot sign in yet.

Checked on the real component in the preview at phone width: switch, one email box, "Did you mean
gmail.com?", the read-back card, no sideways scroll, and no network call before "Yes". **Not run:**
the final "Yes, create my account" tap (it would create a real account) and a wrong-password sign-in
(it would hit the live sign-in with a made-up address). Both are wording changes on existing paths.

### A shared visit says what makes the place special (2026-10-10, 1.506.0)

Chris wanted to share more than the meal. `visitSpecial(restaurant, menuList)` builds
`{ab, src[], sig[], off[], own}` = About this place (<=1200 chars) + up to 3 http(s) sources, signature
dishes (`it.sig`, <=5), off-menu / specials (<=8), and the restaurant's own `house_story` (<=1200);
`buildVisitPayload(..., special)` adds it as `o.sp` unless `special === false`. VisitShareSheet shows one
checkbox, default on, with `visitSpecialSummary` listing exactly what goes; both share paths pass it.
PublishedVisit renders a "What makes it special" card after the meal, each part labelled by whose words
it is. **Decision recorded:** `house_story` was private by design (it is the restaurant's text); Chris
chose to include it on VISIT shares, labelled "from the restaurant". Place shares still do not carry it.
The private `notes` field is never sent (asserted with the switch on and off). No new data category
for the store privacy answers: a shared visit already carried user-authored content.

### Flags on Show English (2026-10-09, 1.504.0)

Chris's idea. When Show English is on, the original dish name carries the restaurant's country flag and
the English name the US flag; the Show English button shows both. Dish NAMES only (descriptions would be
hundreds of flags). **Corrected in 1.505.0:** one pair per dish on whichever line was translated - the
name when its English differs, otherwise the description - because Italian dish names stay Italian and
name-only flags never appeared on Chris's first Italian menu. **Confirmed working on Chris's phone 2026-10-09.** Origin flag = `countryCodeFromAddress(restaurant.address)` (last address segment,
accents folded, English and local spellings in `COUNTRY_CODES`), NOT the menu's language: a Spanish menu
in Mexico gets Mexico's flag. Unknown country -> no flag; a US place -> no origin flag (US on both lines
says nothing). `flagEmoji` builds regional-indicator pairs so the source stays ASCII. Windows renders
flag emoji as letters; check on a phone.

### A visit rename can fix the menu too (2026-10-08, 1.503.0)

When a visit dish's old name matches an item on this place's menu (`findMenuItem`), the Rename dish box
offers "Also fix it on the menu", **unticked by default** (a typo should travel; "medium rare" should
not). Ticked, VisitForm calls `onRenameMenuDish(match, name)` -> App's `renameMenuDish(rid, mid, si, ii,
name)`, the same function Edit dishes now uses (extracted from the MenuDetail JSX), which renames the
menu item and cascades to visits at that place. Road not taken: always fix the menu (personal tweaks
would leak onto it).

### Visit dish rename keeps its photos; a pencil says it's tappable (2026-10-08, 1.502.0)

Tapping a dish name in Edit visit has long opened "Rename dish" (`editDish` / `saveDishRename`); nothing
signalled it, and I told Chris it didn't exist before checking. Now a small pencil follows each name.
**Bug found while checking:** dish photos live in `dishPics` keyed by the lowercased name and the rename
never moved them, so renaming a dish with photos dropped them on save. `saveDishRename` now moves the
entry (capped at `MAX_DISH_PHOTOS`).

### Who a visit was shared with (2026-10-08, app 1.501.0 / backend 0.130.0)

Chris asked how to see who he shared a visit with. In-app sends were already stored (`shares`, payload
carries the visit's shared-record id as `sv`) but never shown; visit LINK opens were not counted at all
(only place links were; I had told him otherwise, and corrected it before building).
`GET /api/shares/activity` returns `{sv: {to:[names], opened, saved}}` for all the caller's shared visits
in one call (History draws every card), scoped to `created_by` / `from_user_id`. The public visit page
now records anonymous `share_events` (kind "visit", slug = sv): "opened" per load in
PublishedVisitLoader, "saved" when someone starts their own visit from a PUBLIC link. History shows
"Sent to ... - link opened N times - saved once" under each shared visit. Counting started 2026-10-08;
3 of 10 early visit sends predate the `sv` id and cannot be matched. Known: the sharer opening their own
link counts. Not on the place page's visit list yet, History only.

### Renaming a menu dish fixes it in your visits there (2026-10-08, 1.500.0)

"Beef Fillet" scanned as "Beef Filler" and was already logged. `onRenameItem` now also renames that dish
in visits to the SAME place (exact old name, plus the picker's "Name (Section)" form), reads visits via
`visitsRef` (a rename straight after logging sees the new visit), and toasts the count. Other places
and hand-typed variants are untouched. Not done: teaching the scan to "correct" misreadings, which
would fight the copy-as-printed rule and could "fix" real unusual names.

### Move a whole menu into another (2026-10-07, 1.499.0)

The way back after a split: `splitMenuSections` refuses to move a menu's last section, so a
one-section split-off menu could never rejoin Main. MenuDetail gets "Move into" (shown when
`otherMenus` is non-empty; target preselected when there is one): App's `onMergeInto` appends the
source's sections to the target, `mergeTranslation`s any translation, removes the source, opens the
target and flashes "Moved into ...". Road not taken: letting Split move the last section out (hides
the way back). New `merge` icon (our own drawing). **Confirmed working on Chris's phone 2026-10-07.**

### Split is findable: info dot + a split icon per section (2026-10-07, 1.498.0)

Chris found Split "not that obvious". An InfoDot sits beside the Split button; each section header in
MenuView gets a split icon (`onSplitSection`, passed only by MenuDetail and only with 2+ sections) that
opens a one-line panel under the section, name prefilled from the section, calling the same
`onSplitMenu([si], name)`. `.msec-head` was a lone `<button>`; it is now inside `.msec-headrow` beside
the icon button (no nested buttons). **Icon: new `split` (our own drawing, a stem branching into two
arrows).** Rendering showed `nodes` reads as Share almost everywhere, so it no longer marks Split.
Group order still uses `nodes`.

### Dish picker: collapsed sections; "/" lists become choices (2026-10-07, 1.497.0)

- Visit-form picker sections start collapsed, one open at a time (`pickOpen`, "menu:section"); a closed
  header shows "N picked". Single-section menus have no header and stay open.
- `choiceParts`: a line with 3+ " / "-separated parts (each <= 60 chars) becomes separate chips; two-part
  names stay whole ("Surf / turf"), unspaced slashes untouched ("AC/DC"). Known imperfection: "Red /
  white / rose wine" -> Red, white, rose wine. Picker only; the saved menu keeps the printed line, so
  `findMenuItem` won't ground a split part's estimate in a menu description.
- Both scan prompts gained an ALTERNATIVES rule (choices on one line -> separate items with the line's
  price; a single slash-named dish stays one), so fresh scans fix it at the source.

### A quiet Translate link on menus that look English (2026-10-07, 1.496.0)

`canTranslate` no longer requires `menuLooksForeign`: any menu not yet confirmed English (`translation.lang
=== "en"`) can be translated. Foreign-looking menus keep the "Show English" pill; others get a small
"Translate" text link in the same place-card spot, so a misjudged foreign menu is never stranded. On a
truly English menu the tap costs one AI request, records `lang:"en"`, and the link disappears for that
menu. Road not taken: the pill on every menu (clutter on English menus).

### A restaurant's own story from a photo (2026-10-07, 1.495.0)

Chris photographed FIRE's "Opposites attract" page and asked where it fits. It belongs in **In their
words** (`restaurant.house_story`), which only ever filled from a menu scan. RestaurantDetail now offers
"Add their story from a photo" / "Replace from a photo" (`onSaveHouseStory`): it reuses `digitizeMenu`
(one AI request, 1600px for small print) and shows the text before saving, because it is presented as
the restaurant's words. Also fixed in Add a menu: a page with **no dishes** used to reach review with zero
sections and save an EMPTY menu (and a re-scan would have crashed on `menusToSave[0]`); now it saves
only the story, is never a replace, and the review card and toast say so.

### The vote that could never be cast (2026-10-07, app 1.494.0 / backend 0.129.0 / DB)

Chris tapped the update banner and got "Where shall we eat?" as an error. Reading the server log
through the Railway plugin unrolled three faults:

1. **Update reload collided with vote links.** `applyUpdate` reloads onto a cache-busting param; it
   was `?v=<version>` since June, and vote links became `?v=<code>` on 2026-08-09. The router's
   `[?&]v=([A-Za-z0-9]+)` read "1.493.0" as vote "1" -> GET /api/group/1 -> 404. Now `?_upd=`, and the
   `v=` / `g=` patterns require the code to end cleanly (`(?=&|#|$)`) because the OLD copy performs the
   reload and the NEW copy parses it; a version-shaped `v=` / `_upd=` is stripped from the address bar.
   `isDeadVote` had masked it: it only drops a code after one failure per device.
2. **No vote ballot could ever save.** `group_orders.id` is uuid; `sql/group_vote.sql` created
   `group_vote_ballots.order_id` as **bigint**. 0 ballots ever, 1 vote created. The vote feature had
   never been tested with real people (see the MenuCaptain memory), which is how it survived.
3. **`group_order_views` never existed live** (`sql/group_seen.sql`, 2026-08-01, never run, and also
   bigint). So "who has opened this order" never worked ("seen not recorded" in the log), and the 30-day
   retention sweep died on it every night (log failures back to 2026-09-30; likely since it shipped
   2026-09-22). The retention promise in the privacy labels was not being kept.

Fixed: migration `group_order_id_types_uuid` (Chris's yes; both tables empty) makes both uuid, creates
the views table with RLS and a service_role grant; repo scripts corrected and the migration kept as
`sql/group_order_id_types_uuid.sql`. The sweep now skips a missing child table (PGRST205) instead of
aborting; any other error still raises. After the redeploy the sweep cleared **46** sessions past
retention to **0**. Swept every table the code names against the live schema: only `device_tokens`
(push) is missing, and push was removed for v1, so it is noted, not built.

**Italy (same release):** detection gains Italian function words (ai, agli, allo, dei, delle, degli,
il, e, nel, sul, sulla), tested on plain Italian (offered) vs an English Italian-American menu (not);
the two-languages rule covers same-line Italian/English and keeps local + English when 3+ languages.

### Menus printed in two languages; Show English at the top (2026-10-07, 1.493.0)

- **Bilingual menus** (La Bona Sort, Barcelona: Spanish pages above English pages). The digitizers'
  new TWO LANGUAGES rule: list each dish once in the local language, return the menu's OWN English as
  `name_en` / `description_en` (section `name_en`), copied word for word, absent on one-language menus.
  `printedEnglish()` lifts them into `menu.translation` (`source:"menu"`, `lang:"printed"`, keyed by
  `trKey` on the normalizer's trimmed wording) BEFORE the normalizer drops unknown fields;
  `_mergeMenus` merges chunk translations; all three save branches attach `result.translation`.
  `mergeTranslation` keeps `source` only when both halves agree. Show English then shows the printed
  English, labelled "English as printed on the menu". Road not taken: asking which language to keep
  (loses one, and pays to AI-translate what the menu already printed). **Untested against a real
  scan of a bilingual board**; the first one is the live test.
- **Placement.** Chris couldn't find Show English (a screen and a half down). It is now a pill in the
  `.menu-head` place card; state + `toggleEnglish` moved to MenuDetail, MenuView takes `showEnglish`.
  Road not taken: an "EN" pill in the sticky fold bar (in reach, but cryptic).

### Places abroad get their city; photo estimates reuse the photo (2026-10-07, 1.492.0)

**Cities.** `cityFromAddress` recognised only a US "City, ST 12345" segment, so every place quick-added
from a search outside the US (Chris, Barcelona) was saved with `location: ""`: no city on the place,
its visits, shared visits (`city: rest.location`) or the city chips. The server's `/api/places/details`
always read cities worldwide from `addressComponents`; only search/nearby quick-adds used the client
parser. Still confidence-gated (a postcode must anchor it; blank beats a guess), now: US and Canada
(city is the segment before), postcode-first in the LAST THREE segments only (Europe, Latin America;
trailing 2-letter province dropped), city-then-postcode (UK, Japan). Earlier segments are the street,
where "1234 Something" is a house number. 19 addresses checked. A sync-time backfill fills BLANK
`location` from the address and writes only when something changed; a typed city is never touched.
`sv.city || cityFromAddress(sv.address)` when logging a visit from someone else's share. Share links
already sent are snapshots and keep the old (blank) city.

**Photo estimates.** Both visit-form estimates always opened the picker even with photos present.
Dish: with dish photos the button reads "Estimate from your photo" and uses the NEWEST (a better shot
added later wins; `alreadyKept` stops it being re-added as a dish photo; the conflict path carries the
flag). Whole plate: thumbnails of the visit's photos, "Which photo shows the food?", plus "Take a new
photo". Guessing the cover was the road not taken (a group-shot cover would loop). `photoSlotBlob`
loads a pending slot from memory or a saved one from the IndexedDB cache, else `ghGetRawFile`.

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
the SAME slip typed twice, nor autofill filling both boxes wrongly. (That box was removed 2026-10-10,
1.507.0; the two layers below are now the whole guard.)

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
**SUPERSEDED 2026-10-10 (1.507.0): that branch and its copy were removed at Chris's request; see the
tripwire in the 1.507.0 section.**

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
