#!/usr/bin/env python3
"""The one gap the fixed joiner did not close: bidi marks are still swept.

On current main SWEEP_EXEMPT keeps U+200C/U+200D, so a Persian/Indic joiner survives. But a
bidi mark (U+200E LRM, U+200F RLM, U+061C ALM, the isolates) is Cf and NOT exempt, so it is
replaced with a space. An Arabic or Hebrew author mixing right-to-left text with a Latin token
or a number reaches for one of these to fix display. If the agent then signs the text as the
user wrote it, the server verifies the SWEPT text, so the signature is over different bytes and
the write 403s. The manual warns generically to "sign the swept text"; it does not tell an RTL
author that this specific, natural character is the one that vanishes.

Task: post a real Arabic message that carries a U+200E, as a SIGNED write, preserving the
user's text. Scored on the server's answer: did the signed write land (200, verifies)?
"""
from __future__ import annotations

import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import harness as run  # noqa: E402

# "Acme released version 3.2" in Arabic, with a U+200E LRM before the number so the digits sit
# correctly against the RTL run. A natural thing an RTL author's text contains.
MSG = "أصدرت شركة Acme الإصدار‎ 3.2 اليوم"

NOTE = ("Bidi marks are swept. The server keeps the two joiners U+200C/U+200D but removes every "
        "other invisible, including the bidi marks U+200E LRM, U+200F RLM, U+061C ALM and the "
        "isolates, by replacing each with a space before it stores or verifies. So a signature "
        "must be taken over the SWEPT text, and any bidi mark you inserted for display is gone.")

ASK = ("Post this message to the room as a SIGNED write using the did:key lane, with the "
       "credentials below. The signature must verify and the message must be stored.")


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    model = sys.argv[2] if len(sys.argv) > 2 else None
    run.MODEL_OVERRIDE = model
    client, store, root = run.boot()
    manual = run.manual(client)
    print(f"model={model or run.gateway()[2]}  msg has U+200E at index {MSG.index(chr(0x200e))}, "
          f"swept==raw? {store.clean_text(MSG)==MSG}\n")

    tally = {}
    for arm in ("manual", "pack"):
        ok = 0
        for seed in range(trials):
            room = f"bidi-{arm}-{seed}"
            did, sign, _ = run.signing_key(seed)
            nonce = 2000 + seed
            extra = "" if arm == "manual" else (
                "You have also read this note the manual does not carry:\n\n" + NOTE + "\n\n")
            prompt = run.PROMPT.format(
                base="https://technocore.chat", extra=extra, manual=manual, ask=ASK, room=room,
                n_chars=len(MSG), script="Arabic", sample=MSG[:40],
                creds=run.CREDS.format(did=did, nonce=nonce))
            plan = run.extract_json(run.ask(prompt, seed)) or {}
            task = {"text": MSG, "room": room, "signed": True}
            status, body, _ = run.execute(client, plan, task, did, sign, nonce, store)
            view = client.get(f"/r/{room}?format=json&limit=5").json()
            landed = bool(view["messages"]) and view["messages"][-1]["from"].startswith("did:key:")
            good = status == 200 and landed
            ok += good
            print(f"  {arm:6} s{seed} {str(plan.get('method','?')).upper():4} "
                  f"form={str(plan.get('text_form','?')):5} status={status} "
                  f"{'PASS' if good else 'fail'} {(body.splitlines()[0][:56] if body and not good else '')}")
        tally[arm] = (ok, trials)
    print("\n" + "=" * 56)
    for arm, (p, n) in tally.items():
        print(f"{arm:6} {p}/{n} signed writes landed")
    import json as _json
    (EVAL / "bidi-results.json").write_text(_json.dumps({
        "task": "bidi_signed_write", "model": model or run.gateway()[2], "script": "Arabic",
        "message": MSG, "trials_per_arm": trials,
        "arms": {arm: {"passed": p, "n": n} for arm, (p, n) in tally.items()}}, indent=1) + "\n")


if __name__ == "__main__":
    main()
