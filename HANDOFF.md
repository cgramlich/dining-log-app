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

## Current state — 2026-09-24

| Piece | Version | Where |
|---|---|---|
| Web app | **1.472.0** | menucaptain.com (GitHub Pages), confirmed live |
| Backend | **0.123.0** | Railway, `/health` reports `db connected` |
| Native shell | **1.472.0** | built and pushed, **not yet submitted to any store** |

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
