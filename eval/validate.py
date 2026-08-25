#!/usr/bin/env python3
"""Quick hypothesis check before the full build.

The manual gives ONE non-Latin URL-budget figure (CJK = 9 bytes) and no threshold. Take an
Arabic message that is UNDER the documented 4096-character cap but OVER the ~16 KB URL edge on
the GET lane. The manual says "4096 characters fit" and "use POST for long non-Latin" with no
number, so an agent must decide the lane itself. Does a capable agent GET it (and have it die
at the edge) with the manual alone, and POST it when the guide hands it the measured Arabic
ceiling? Measured against a real instance of the service, scored on what actually landed.
"""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import harness as run  # noqa: E402  boot, ask, extract_json, gateway, execute, PROMPT

EDGE = 16 * 1024

# ~3,400 Arabic characters: under the 4096-char cap, but at ~6 URL bytes/char it is ~20 KB of
# URL, so the GET lane cannot carry it. Sweep-stable: no leading/trailing space, no bidi mark,
# so the ONLY thing that can fail the trial is the lane decision.
UNIT = "مرحبا بالعالم هذه رسالة تجريبية مطولة باللغة العربية "
ARABIC = (UNIT * 66).strip()

NOTE = ("Arabic is written in a 2-byte script: one Arabic character costs about 6 bytes once "
        "URL-encoded, so a signed GET carries roughly 2,900 characters and an unsigned GET "
        "roughly 2,930, far below the 4096-character message cap. A longer Arabic message is "
        "within the character cap but past the ~16 KB URL edge, so it must go by POST.")

ASK = "Post this message to the room. It must be stored complete and unaltered."


def score(client, plan, room, text):
    method = str(plan.get("method", "GET")).upper()
    # rebuild the URL length the harness would send, to model the edge the TestClient ignores
    path = str(plan.get("path", ""))
    approx = len(path) + (len(urllib.parse.quote(text, safe="")) if "TEXT" in path else 0)
    if method == "GET" and approx > EDGE:
        return False, f"GET ~{approx}B > 16KB edge: dies before the service sees it"
    view = client.get(f"/r/{room}?format=json&limit=5").json()
    if not view["messages"]:
        return False, "nothing stored"
    stored = view["messages"][-1]["text"]
    if stored == text:
        return True, f"stored {len(stored)} chars intact by {method}"
    return False, f"altered: stored {len(stored)} of {len(text)}"


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    client, store, root = run.boot()
    manual = run.manual(client)
    _, _, model = run.gateway()
    print(f"model={model}  arabic_chars={len(ARABIC)}  "
          f"url_bytes={len(urllib.parse.quote(ARABIC, safe='')):,}  cap={store.MAX_TEXT_CHARS}\n")

    tally = {}
    for arm in ("manual", "pack"):
        for seed in range(trials):
            room = f"val-ar-{arm}-{seed}"
            extra = ""
            if arm == "pack":
                extra = ("You have also read this language-specific onboarding note the manual "
                         f"does not carry:\n\n{NOTE}\n\n")
            prompt = run.PROMPT.format(
                base="https://technocore.chat", extra=extra, manual=manual, ask=ASK, room=room,
                n_chars=len(ARABIC), script="Arabic", sample=ARABIC[:40], creds="")
            reply = run.ask(prompt, seed)
            plan = run.extract_json(reply)
            if plan is None:
                ok, why = False, f"no_json: {reply[:80]}"
                method = "-"
            else:
                task = {"text": ARABIC, "room": room, "signed": False}
                run.execute(client, plan, task, None, None, 0, store)
                method = str(plan.get("method", "?")).upper()
                ok, why = score(client, plan, room, ARABIC)
            tally.setdefault(arm, [0, 0])
            tally[arm][0] += 1
            tally[arm][1] += 1 if ok else 0
            print(f"  {arm:6} seed {seed}  {'PASS' if ok else 'fail'}  {method:5} {why}")
    print("\n" + "=" * 60)
    for arm, (n, p) in tally.items():
        print(f"{arm:6} {p}/{n} passed")
    import json as _json
    (EVAL / "budget-results.json").write_text(_json.dumps({
        "task": "url_budget", "model": model, "script": "Arabic",
        "message_chars": len(ARABIC), "url_bytes": len(urllib.parse.quote(ARABIC, safe="")),
        "cap": store.MAX_TEXT_CHARS, "trials_per_arm": trials,
        "arms": {arm: {"passed": p, "n": n} for arm, (n, p) in tally.items()}}, indent=1) + "\n")


if __name__ == "__main__":
    main()
