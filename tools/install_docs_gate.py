# -*- coding: utf-8 -*-
"""Install the release docs gate as this repo's pre-push hook (2026-10-16).
Hooks are not versioned, so a fresh clone needs this once:
    python tools/install_docs_gate.py
"""
import os, stat
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hook = os.path.join(REPO, ".git", "hooks", "pre-push")
body = ("#!/bin/sh\n"
        "# MenuCaptain release docs gate. See tools/release_docs_gate.py. Never --no-verify.\n"
        "cd \"$(git rev-parse --show-toplevel)\" || exit 1\n"
        "exec python tools/release_docs_gate.py\n")
with open(hook, "w", newline="\n") as f:
    f.write(body)
os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print("installed", hook)
