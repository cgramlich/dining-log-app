# Dining Captain - User Guide

Dining Captain is your private notebook for eating out. You log the places you go,
scan their menus, remember which dishes you loved, and - if you want - get a
rough idea of the calories on your plate. It is built to help you *remember and
enjoy* what you eat, not to police it.

Everything you save lives in your own private storage, separate from everyone
else’s. You, and anyone you set up, each have a completely separate world even
though you all open the same app.

-----

## Getting set up

The first time you use the app you enter four things on the Settings screen:
your GitHub username, your repository name, an access token, and an Anthropic
key (which powers the AI features). The app then creates your data files
automatically on your first save.

If you are setting up a new person from scratch, follow the separate
“Private Repo Setup” guide - it walks through creating the account, the repo,
and the token step by step. You only do this once.

-----

## Getting around

There is a bar across the bottom of the screen with four spots:

- **History** - everything you have logged, newest first.
- **Places** - your list of restaurants.
- **The plus (+) button** - the quick-action button. Tap it to log a visit,
  add a restaurant, or scan a menu.
- **Settings** - your account details, the update check, this user guide, and
  app info.

-----

## Places (your restaurants)

**Adding a place.** Add a restaurant with its name, cuisine, city, address,
phone, website, and any notes. You can mark it as a favorite and give it a
photo. Only the name is required - everything else is optional.

**Find address.** When adding or editing a place, tap **Find address** under
the address field and the app looks it up by name and city, fills in the
address, and remembers its location for the map. When the place is well listed
on the map, it also fills in any details it can find - phone, website, cuisine,
and hours - but only for fields you have left blank, so it never overwrites
what you typed. It finds chains and well-mapped spots reliably; for a brand-new
or tiny place it may come up empty (or with just the address), in which case
just fill in the rest yourself.

**The restaurant page.** Opening a restaurant shows its details, its menus,
every visit you have logged there, and a picks card once you have rated some
dishes (see “Your picks” below).

-----

## Map

Tap **Map** at the top of Places to see your restaurants as pins on a map.
Favorites show in the accent color, everything else in a softer tone. Tap a
pin to see the name and a button to open that restaurant.

The first time you open the map, any place that has an address but no pin yet
is located automatically, one at a time - you will see them appear over a few
seconds, with a “Locating your places” note at the bottom. Each place is only
located once and then remembered, so it is instant after that. If you change a
place’s address later, the map quietly re-locates it.

If the active city filter is set on the Places tab, the map shows just that
city. Places with no address (or one that could not be found) are not pinned;
the bottom of the map tells you how many are not mapped.

-----

## Menus

**Scanning a menu.** Use “Scan a menu” and take or pick photos of the physical
menu. The app reads it and turns it into a clean, digital menu - sections,
dish names, descriptions, prices, and tags. This is what powers “Help me order”
and the calorie estimates.

**More than one menu.** A place can have several menus (for example Dinner,
Brunch, and Drinks). When you scan a menu that has more than one section, the
app asks how to save it: **One menu** keeps every section together in a single
menu, or **Customize each section** lets you split the sections into separate
menus (any sections you give the same name merge back together). That is how
one long scan can become a few tidy menus.

**Where menus show.** On a restaurant page, if there is only one menu it is
shown expanded right there, so you can browse and estimate items without
tapping in. With two or more menus, each appears as a card you tap to open.

**Re-scanning and deleting.** You can re-scan a menu to replace it with a fresh
version, or delete a menu you no longer want. (For a single inline menu, use
the **Manage** button by the Menus heading to reach those options.) Re-scanning
replaces the old copy, so any estimates saved on the old items are not carried
over.

**Calories on a menu.** If the menu itself prints calories, the app captures
those and shows them as a real number labeled “per menu.” If it does not, you
can tap “Estimate calories” on an item and the app will estimate it from the
dish description. Estimated numbers are always shown with a “~” and marked EST
so you can tell them apart from real ones.

-----

## Help me order

On any digitized menu you can ask a plain-English question - things like
“something healthy,” “not too heavy,” “best value,” or “what did I love here?”
The app answers using that restaurant’s actual menu, and it takes your own
dish ratings into account, so the more you log the more personal the answers
get. When a menu item has calories on it - whether printed on the menu or
estimated - the answers factor those in too, so a question like “something
lighter” can weigh the actual numbers. It stays easygoing about it: the
calories inform the suggestion, they are never treated as a budget or a rule.

-----

## Logging a visit

Tap the plus button and choose “Log a visit.” You can fill in as much or as
little as you like:

**Date and rating.** Pick the date and give the visit a star rating. You can
rate in half-stars: tap the left side of a star for a half, the right side for
a whole. Tap the rating you already have to clear it. You rate each visit, not
the restaurant - so a place can have a different rating every time you go. On a
restaurant, in the Places list, and on a shared card, the star number shown is
the average of your visits there, labelled “avg.”

**What you had (dishes).** Add the dishes you ordered, either by typing them or
by tapping them straight from that restaurant’s digitized menu. Tapping from
the menu is the better habit - it makes the rest of the features line up
correctly (see the photo estimate below).

**Again or Skip.** Each dish has an “Again” and a “Skip” button. Tap Again for
something you would order again, Skip for something you would not. This is the
heart of the app - it is how you remember what is worth getting next time. The
most recent verdict always wins, so you can change your mind later.

**Estimate a dish from a photo.** Under each dish is an “Estimate from a photo”
button. When the food arrives, tap it and snap a picture of that dish. The app
estimates the calories and macros for it. If that dish is on the restaurant’s
digitized menu, the estimate (and a thumbnail of your photo) is saved onto the
menu item too - so the next time you open that menu, the picture and the
numbers are already there. If that menu item already had an estimate, the app
asks whether to keep the old one or use your new photo. Estimating works best
when you added the dish by tapping it from the menu, so the names match.

**Estimate without a photo.** Did not snap a picture? Each dish also has an
“Estimate without a photo” option that estimates from the dish name - grounded
by the menu description when you tapped the dish from the menu, so it is a
better guess than the name alone. Tap “Redo” on any estimate to clear it and
choose either method again.

**Running total.** Once you have estimated a dish, a calm total appears in the
visit (“~610 cal total - 31P / 63C / 22F across 2 dishes”) so you can watch it
add up as you log - a number for memory, never a budget.

**Estimate the whole plate.** If your meal is not on a menu, there is also a
“Estimate from a photo” option for the whole plate, which gives one set of
numbers for the meal. You can edit any estimate by hand if you know the real
figures.

**Photos and notes.** Attach photos of the visit and jot down any notes.

-----

## History

History is the running list of everywhere you have eaten, newest first. Each
entry shows the rating, the dishes (color-coded by your Again/Skip verdict,
with the estimated calories beside each one when you have them), any nutrition
summary, your notes, and your photos. When you have estimated two or more
dishes on a visit, the entry also shows a calm running total (for example
“~1,240 cal total across 3 dishes”) - a number for memory, never a budget.

-----

## Searching

As your lists grow you can filter them quickly:

- On **History**, the search box at the top filters your visits by restaurant
  name, by dish, or by anything in your notes.
- On **Places**, the search box filters your restaurants by name, cuisine, or
  city, and works alongside the city filter chips. A **Sort** row lets you order
  them alphabetically (A-Z), by recently added, or favorites first - and the
  sort and search both work within whichever city you have selected.

Type to filter instantly; tap the (x) to clear it and see the whole list again.

-----

## Your picks (what you loved)

Once you have rated a few dishes at a place, its restaurant page shows a
picks card with two parts:

- **You’ve loved these here** - the dishes you have marked Again, so you can
  reorder your favorites without thinking.
- **Last time** - a quick reminder of your most recent visit.

Marking a dish Skip just keeps it off the loved list. Not ordering something
again does not count against it.

-----

## Your Year in Food

Open **Your Year in Food** from the top of your **History** tab, or from
**Settings** - either way you get a recap built entirely from what you have
logged - a calm look back rather than a scoreboard.

At the top you can switch between any year you have visits in, plus **All
time**; it opens on your most-logged year so there is always something to see.
The recap can include:

- how many visits you logged, and how many different places they were
- new spots you discovered that year
- the cities you ate in
- your #1 spot - where you went the most
- your top cuisine
- your most-loved dish, with the other dishes you marked Again
- your highest-rated visit
- your busiest month

Each card only appears when there is something to show, so a quiet year stays
short. There is no calorie total here, on purpose - in keeping with the spirit
of the app, the recap is about places, dishes, and memories, not a number to
measure yourself against.

You can share the recap as an image: tap the **share** icon at the top and the
app renders the year you are viewing onto a card you can text or post.

-----

## Your food passport

**Food passport** is a photo gallery of everywhere you have eaten - open it from
the top of your **History** tab, or from **Settings**. Every photo you have
added, whether to a whole visit or to a single dish, shows up as a tile, grouped
by month with the newest first. Tap any photo to jump straight to that visit.

Think of it as the picture-first companion to History: History is the detailed
log, the passport is the gallery. The first time you open it, photos that are
not cached yet load over a few seconds, and are quick to view after that.

-----

## Sharing a place

On a restaurant page, tap the **share** icon at the top (next to the favorite
star) to turn that place into a shareable card - its photo, name, your rating,
the address, and the dishes you have loved there. The app builds the card as an
image and hands it to your phone’s share sheet, so you can text it to a friend,
save it to Photos, or post it.

It is just a picture, so the person you send it to does not need the app or any
access to your data - they simply get your recommendation. If a place has no
photo yet, the card uses a colored header instead.

-----

## Publishing a list

Want to send someone your favorites? On the **Places** tab tap **Publish a
list**, give it a title, and tick the restaurants to include (your favorites and
highest-rated are listed first). Tap **Create link**, then **Copy** or **Share**.

When you publish, the app creates a small public page for the list and gives
you a short link to it - and when you text that link, it shows a proper
preview card with your list’s name instead of a random web address. The first
time a particular list is published, its page can take up to a minute to go
live; anyone who taps right away sees a brief “almost ready” note that opens
the list automatically. Sharing the same list again later is instant.

If the app cannot create the short page (it needs permission to the app’s
repository - some accounts will not have that), it simply shares the
full-length link instead, which always works; a **Shorten** button appears for
those long links if you want a tidier one.

**One-tap city share.** If you have a city selected in the Places filter, a
**Share my [city] spots** button appears. Tap it and the app builds a list of
just that city’s places and opens your share sheet straight away - no titling or
ticking needed.

The whole list is public once shared, so whoever you send it to just taps it
and sees your picks - each place with its city, cuisine, your rating, the
dishes you loved there, and the address with a **Directions** link that opens
their maps app. They do not need the app, an account, or any access to your
private data, and the link never carries your token or key. Treat anything you
publish as public: the link can be opened by anyone who has it, the published
page lives in the app’s public repository, and it includes the street address
of each place you share.

The shared view is text-only - no photos or private notes - so it stays light
and loads instantly.

-----

## Understanding the calorie labels

A few small labels show up wherever calories appear:

- **~320 cal** - the “~” means this is an estimate.
- **850 cal, per menu** - a real number printed on the menu (no “~”).
- **EST** - short for estimated.
- **9P / 22C / 22F** - grams of protein, carbs, and fat.

Where an estimate came from:

- **from a photo** - estimated from a picture of the actual plate.
- **estimated** - estimated from the menu description (no photo).
- **per menu** - taken straight from the printed menu.
- **entered by you** - a number you typed in by hand.

A photo of the real plate is treated as a better guess than one from the
description, which is why the app offers to replace a description-based
estimate when you add a photo.

-----

## Keeping the app up to date

When a new version is published, the app notices on its own and shows an
“Update available” banner - tap it to refresh to the latest version. You can
also check any time from Settings with “Check for updates.” This is what spares
you from the usual home-screen app trick of having to clear it and re-add it to
get the newest changes.

-----

## Your data, privacy, and cost

Your logs, menus, and photos are stored in your own private storage - they are
not shared with anyone else, and each person you set up has a separate world.

The AI features (menu scanning, Help me order, and the photo estimates) run
through your own Anthropic key, so those requests are yours. Personal-scale use
costs only pennies. The photo estimate is the most involved AI step, since it
has to look at a picture; everyday use is still very cheap.

-----

## If something stops working

- **Nothing is saving / it says it can’t sync.** Your access token has most
  likely expired. Generate a fresh token and paste it into Settings - that is
  the usual fix. (Tokens are set to expire on a schedule for safety.)
- **A photo is slow to appear or won’t load.** Photos load from your storage
  the first time, so the very first view can be slow; it is quick after that.
  If one refuses to load, it may not have finished uploading - try again on a
  good connection.
- **An AI feature says to add your key.** The Anthropic key in Settings is
  missing or wrong. Re-enter it.
- **A dish photo estimate didn’t show up on the menu.** The dish name has to
  match a menu item exactly. Adding the dish by tapping it from the menu
  guarantees the match; a free-typed name that doesn’t match will still get an
  estimate on the visit, it just won’t attach to the menu item.

-----

## The spirit of the app

The calorie and macro numbers are here for curiosity and memory - a record of
what you ate, not a budget to stay under. The app will never scold you, warn
you, or tell you that you “blew” anything. If the numbers ever start to feel
like pressure rather than interest, ignore them - the dish ratings and the
memories are the real point.

-----

*Maintainer note: this document is the source of truth for the app’s in-app
help. When features change, update this file first; the in-app Help screen and
the (i) call-outs are meant to be rebuilt from it so the two never drift.*