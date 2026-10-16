# -*- coding: utf-8 -*-
"""MenuCaptain release docs gate (2026-10-16).

Chris, again: "all of our documents updated from user and help guides to
promotion featured links and docs ... should always be updated, and I've
mentioned this many times." Memory was not enough, so this makes it
mechanical. Run by .git/hooks/pre-push (install: python tools/install_docs_gate.py).

A push is REFUSED unless, for the app version at HEAD (APP_VERSION in
index.html):
  1. releases.json at HEAD has an entry for it, and every field (guide, promo,
     email_notes, welcome, handoff) says "updated..." or "n/a: <why>";
  2. HANDOFF.md at HEAD shows that version in its table;
  3. the living promo inventory on this PC says data-inventory-as-of that
     version (it lives in Dropbox, not git), and every version since the last
     one has a promo field, so the stamp cannot move without an account;
  4. menucaptain-help.md at HEAD was exported from the same guide (its text
     contains the guide's last paragraph heading as exported).
The road not taken: checking whether the WORDS are right. No script can; the
entry makes the decision explicit and reviewable, which is what was missing.
Never bypass with --no-verify; fix the entry instead.
"""
import json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMO = r"C:\Users\cjgra\Dropbox\My AI\CG Apps\MenuCaptain\MenuCaptain Promo\living-promo-template.html"
FIELDS = ("guide", "promo", "email_notes", "welcome", "handoff")


def at_head(path):
    try:
        return subprocess.run(["git", "show", "HEAD:" + path], cwd=REPO, capture_output=True,
                              check=True).stdout.decode("utf-8", "replace")
    except subprocess.CalledProcessError:
        return None


def vkey(v):
    return tuple(int(x) for x in v.split("."))


def check(version=None, promo_path=PROMO):
    problems = []
    index = at_head("index.html") or ""
    mm = re.search(r'const APP_VERSION\s*=\s*"([0-9.]+)"', index)
    if not mm and not version:
        return ["could not read APP_VERSION from index.html at HEAD"]
    ver = version or mm.group(1)
    raw = at_head("releases.json")
    try:
        rel = json.loads(raw) if raw else {}
    except ValueError as exc:
        return [f"releases.json is not valid JSON: {exc}"]
    entry = rel.get(ver)
    if not isinstance(entry, dict):
        problems.append(f"releases.json has no entry for {ver}. Add one: for each of "
                        f"{', '.join(FIELDS)} say 'updated: what' or 'n/a: why'.")
    else:
        for f in FIELDS:
            val = str(entry.get(f, "")).strip()
            ok = val.lower().startswith("updated") or (val.lower().startswith("n/a:") and len(val) > 8)
            if not ok:
                problems.append(f"releases.json {ver}.{f} must say 'updated...' or 'n/a: <why>' (has: {val!r})")
    handoff = at_head("HANDOFF.md") or ""
    if f"**{ver}**" not in handoff:
        problems.append(f"HANDOFF.md at HEAD does not show **{ver}** in its version table")
    if promo_path and os.path.exists(promo_path):
        promo = open(promo_path, encoding="utf-8").read()
        pm = re.search(r'data-inventory-as-of="([0-9.]+)"', promo)
        as_of = pm.group(1) if pm else ""
        if as_of != ver:
            problems.append(f"promo inventory says data-inventory-as-of=\"{as_of}\", not {ver}: review the "
                            f"inventory for every release since, then move the stamp")
        versions = sorted((k for k in rel if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", k)), key=vkey)
        missing = [k for k in versions if vkey(k) <= vkey(ver)
                   and not str((rel[k] or {}).get("promo", "")).strip()]
        if missing:
            problems.append("promo field missing for " + ", ".join(missing))
    helpmd = at_head("menucaptain-help.md")
    if helpmd is None:
        problems.append("menucaptain-help.md is not in the repo: run node export_help.js in menucaptain-native-build")
    else:
        # Every paragraph heading in the in-app guide (HELP_DOC) must be in the export.
        a = index.find("const HELP_DOC = `")
        b = index.find("`;", a) if a >= 0 else -1
        guide = index[a:b] if a >= 0 and b > a else ""
        heads = re.findall(r"\n\*\*([^*\n]{3,60})\.\*\*", guide)
        stale = [h for h in heads if h not in helpmd]
        if not guide:
            problems.append("could not find HELP_DOC in index.html")
        elif stale:
            problems.append("menucaptain-help.md is older than the guide (missing: " + "; ".join(stale[:3])
                            + "): run node export_help.js in menucaptain-native-build")
    return problems


if __name__ == "__main__":
    args = sys.argv[1:]
    version = args[args.index("--version") + 1] if "--version" in args else None
    probs = check(version)
    if probs:
        print("\nRELEASE DOCS GATE: push refused. Documents first:\n")
        for p in probs:
            print("  - " + p)
        print("\nFix these, commit, and push again. (Never --no-verify.)\n")
        sys.exit(1)
    print("Release docs gate: OK")
