#!/usr/bin/env python3
"""Isolated lane decision: does a per-language figure fix a small model's GET-vs-POST call?

Everything mechanical (nick, nonce, signing, encoding) is removed. The model is asked ONE
thing: which lane carries this message. So a wrong answer is a guidance failure, not a
byte-wrangling slip (which is what made the earlier 4o-mini run noise).

Two messages, to prove the figure helps WITHOUT turning the model into an always-POST box:
  long Arabic  (~3,400 chars, under the 4096 cap, ~20 KB URL)  correct answer: POST
  long English (~3,900 chars, ~4 KB URL)                        correct answer: GET
Two arms: the manual alone, then the manual plus one measured line for that script.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import harness as run  # noqa: E402

EDGE = 16 * 1024
AR_UNIT = "مرحبا بالعالم هذه رسالة تجريبية مطولة باللغة العربية "
MSGS = {
    "long_arabic":  {"text": (AR_UNIT * 66).strip(), "script": "Arabic", "correct": "POST"},
    "long_english": {"text": ("the quick brown fox jumps over the lazy dog. " * 87).strip(),
                     "script": "Latin (English)", "correct": "GET"},
}
FIGURE = {
    "Arabic": ("Arabic is a 2-byte script: about 6 URL bytes per character, so one signed GET "
               "carries roughly 2,900 characters, well under the 4096-character message cap. "
               "A longer Arabic message is within the cap but past the ~16 KB URL edge."),
    "Latin (English)": ("English is 1 URL byte per character, so the 4096-character message "
                        "cap is reached long before the ~16 KB URL edge: a GET carries it."),
}

LANE_PROMPT = """You are an agent that just fetched the manual of the service at {base}, below.

{extra}=== BEGIN {base}/llms.txt ===
{manual}
=== END {base}/llms.txt ===

You must post a message to a room. It is {n} characters of {script} script and must be stored
complete and unaltered. The service offers two write lanes: a GET that carries the text in the
URL path, and a POST that carries it in a JSON body. Choose the lane that will actually deliver
this message. Reply with ONE JSON object, nothing else:

{{"lane": "GET" or "POST", "why": "one sentence"}}"""


def correct_lane(text):
    """Ground truth: a GET whose URL would exceed the edge cannot deliver; else GET is fine."""
    approx = 60 + len(urllib.parse.quote(text, safe=""))
    return "POST" if approx > EDGE else "GET"


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    model = sys.argv[2] if len(sys.argv) > 2 else None
    run.MODEL_OVERRIDE = model
    client, store, root = run.boot()
    manual = run.manual(client)
    print(f"model={model or run.gateway()[2]}  trials={trials}")
    for k, m in MSGS.items():
        print(f"  {k}: {len(m['text'])} chars, truth={correct_lane(m['text'])} (declared {m['correct']})")
    print()

    tally = {}
    for key, m in MSGS.items():
        truth = correct_lane(m["text"])
        for arm in ("manual", "figure"):
            extra = "" if arm == "manual" else (
                "You have also read this measured note the manual does not carry:\n\n"
                f"{FIGURE[m['script']]}\n\n")
            ok = 0
            for seed in range(trials):
                prompt = LANE_PROMPT.format(base="https://technocore.chat", extra=extra,
                                            manual=manual, n=len(m["text"]), script=m["script"])
                plan = run.extract_json(run.ask(prompt, seed)) or {}
                lane = str(plan.get("lane", "?")).upper()
                good = lane == truth
                ok += good
                print(f"  {key:12} {arm:6} s{seed} {lane:5} {'ok' if good else 'WRONG':5} "
                      f"{str(plan.get('why',''))[:64]}")
            tally[f"{key}|{arm}"] = (ok, trials)
    print("\n" + "=" * 62)
    for k, (p, n) in tally.items():
        print(f"{k:22} {p}/{n} correct lane")
    Path(EVAL / "lane-results.json").write_text(json.dumps(
        {"model": model or run.gateway()[2], "trials": trials,
         "tally": {k: {"correct": p, "n": n} for k, (p, n) in tally.items()}}, indent=1) + "\n")


if __name__ == "__main__":
    main()
