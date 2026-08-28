# MenuCaptain — BRIEFING

**Deck-ready. Written to leave the machine.** Accurate as of 2026-08-28. Derived from
`HANDOFF.md`; if a figure differs, the handoff is right and this is stale.

Every person and restaurant named in this file is **fabricated** and labelled as such. No real
user data appears here.

---

## The arc

**Situation.** Eating out generates a surprising amount of memory worth keeping — what you
ordered, whether it was any good, who you were with, what it cost — and almost all of it is lost.
The photos scatter into a camera roll. The dish name is gone by the next visit. The question
"what did I have here last time?" has no answer.

**Problem.** The category is dominated by review platforms, which are built for the *next*
stranger rather than for you. They want your rating in public and give you back a crowd average.
Nobody is building the private version: a notebook that remembers your own eating.

**What was done.** MenuCaptain reads restaurant menus — scanned, photographed, or from a link —
and turns them into structured, searchable data. On top of that sits a personal log: dishes,
photos, ratings, notes, who you were with, what it cost. Around it sit the things eating out
actually needs but nobody has: split the check from a photo of the receipt, run a group order
where everyone adds their own picks from the real menu, and settle "where shall we eat?" with a
vote that needs no app and no account.

**What it means now.** It is live at **menucaptain.com**, installable, and in daily real use.
The billing infrastructure is live. The remaining work before the app stores is administrative
rather than technical.

---

## Concrete figures

| Figure | Value | As of |
|---|---|---|
| Web app | v1.430.0, live | 2026-08-28 |
| Backend | v0.119.0, live | 2026-08-28 |
| Front end | a single HTML file, ~1.38 MB, no build step | 2026-08-28 |
| Backend | ~7,500 lines of Python (FastAPI) | 2026-08-28 |
| Free tier | 75 AI calls + 15 Discovery lookups, lifetime | current |
| Pro | $2.99/month or $19.99/year | current, live in Stripe |
| Cost of a fully-consumed free tier | ~$2.30 per user | modelled |
| AI model, all six tasks | Claude Sonnet 5 | since 2026-08 |

**The free tier is priced as customer acquisition cost, not as a trial.** A user who exhausts it
entirely costs about $2.30. That is a deliberate, bounded number — the tier is metered by *spend*
rather than by days or by feature gates, so the cost of a free user cannot run away.

---

## Quotable claims — each survives a follow-up question

> The free tier is a marketing budget with a hard ceiling, not a countdown.

> Everything is metered by what it costs us, not by what day it is.

> The group vote works with no app and no account. That is the point: the person who has to be
> talked into installing something is exactly the person who won't vote.

> A wrong guess produces no error message. It just quietly describes the wrong person for ever.

> A receipt total is often more correct than the sum of the items — service charges, comps and
> corkage are on the bill and not in the list. So the app shows you the disagreement rather than
> silently overwriting either number.

> One HTML file. Deploying is a git push.

---

## The engineering angle worth a slide: it refuses to guess

This is the most defensible thing about the product and it is unusual enough to lead with.

MenuCaptain repeatedly declines to infer something it could plausibly infer, because the failure
mode of a wrong inference is **silent**. Three examples:

1. **Linking a guest to a person.** When somebody orders as "Sam" and you have a contact called
   Sam Whitaker *(fabricated names)*, the app will not merge them. It asks, once, and remembers
   the answer for ever. The database schema itself enforces this — the field recording *how* a
   link was made has no legal value meaning "guessed."
2. **Suggesting what a friend usually orders.** The suggestion is drawn only from meals they ate
   **with you**. Their history with anyone else is not reachable by any part of the system.
3. **"You usually get."** It stays silent until there are two visits and a genuine repeat.
   Ordering two of something once is not a habit, and the app will not call it one.

The through-line: **an inference that is wrong and invisible is worse than no inference.** Most
products in this space make the opposite trade.

---

## What deserves a picture

- **Before / after of the core loop.** A photographed paper menu on one side; the same menu as
  structured, searchable, taggable dishes on the other. This is the product in one image.
- **The group vote flow.** Host picks 2–5 places → sends one link → everyone ticks what they'd be
  happy with → approval-voted winner. Shows the no-account claim rather than stating it.
- **The cost-metered free tier.** A bar capped at ~$2.30 per free user, contrasted with an
  unbounded time-based trial. Makes the unit-economics argument visually in one beat.
- **The "refuses to guess" moment.** A single UI card asking "is this the same person?" with the
  two names side by side. Small, human, and carries the whole design philosophy.
- **Architecture, if the audience is technical.** One HTML file → GitHub Pages; FastAPI on
  Railway; Postgres with row-level security on and no policies, so only the backend can read.

---

## Angles by audience

**Investor.** Category is dominated by public review platforms; the private layer is unbuilt.
Costs are bounded by design — a free user cannot cost more than the tier allows, and every AI
model must have a price registered before it can be called at all. Infrastructure is deliberately
cheap: one static file plus one small backend.

**Operator / team.** Built by one person with an AI pair, shipping multiple versions a day
against real use. The version numbers in this document moved 30+ times in the last fortnight,
each one a real fix found by using the product rather than by testing it.

**Design.** The product's opinions are visible in its details: two typographic tiers so a long
form has a shape; error messages that name the actual reason instead of guessing; and a rule that
no screen may be a dead end — every failure state carries a way out.

**Technical.** Single-file front end with no build step, so deployment is a push and there is no
bundler to break. Row-level security enabled with zero policies on every table, so a leaked
public key reads nothing. Every AI model priced in an allow-list that doubles as the billing
guard.

---

## Do not say

- **No real user data, ever.** No account names, no real people from the visit log, no real
  restaurant customer information. Every example here is fabricated and marked.
- **No Stripe identifiers**, price IDs, product IDs or customer references.
- **No hostnames, endpoints, keys or environment variables.** Naming the platforms is fine and
  useful in an architecture slide; the actual backend hostname, database and storage bucket are
  not.
- **Do not quote a user count or revenue figure.** There is no public traction number, and the
  free/paid split is not yet meaningful. Say "in daily real use" and stop.
- **Do not claim store availability.** It is not in the App Store or on Google Play. It is a live
  web app with a native shell built and ready to submit.
- **Do not present the pricing as final.** $2.99/$19.99 is what is live today; a change is
  prepared but not shipped. Quote only what is live, or omit price entirely.
- **Do not name the AI vendor's commercial terms**, only the model in use.
