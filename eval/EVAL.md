# The eval

Issue [#116](https://github.com/flop-labs/technocore-chat/issues/116) proposed a translated
onboarding guide and was closed with one ask: *"Is there an example where current guide for
agents is not followed/understood by agent? Please reopen with eval example where it improves
onboarding."* This is that eval, and it reports what it found rather than what would help the
case.

## How a trial works

Every trial runs against a real instance of the service booted from its own source: its own
`TestClient`, the real `MAX_TEXT_CHARS`, the real `clean_text`, the real signer. No mocks. The
model is handed the service's own `/llms.txt` verbatim, which is what an agent onboarding today
actually reads, then asked to perform a task. It replies with one JSON object describing a single
HTTP request. The harness substitutes the real text, signs if asked, sends it, and scores the
**server's** answer and what landed in the room. No credit for explaining the right thing while
emitting the wrong request.

Two arms: `/llms.txt` alone, then `/llms.txt` plus one measured line from the guide for that
script. The scripts are in this directory:

```bash
python3 eval/validate.py 3          # url budget: a long non-Latin message, which lane
python3 eval/lane.py 3              # isolated lane decision, capable model
python3 eval/lane.py 3 gpt-4o-mini  # the same, on a small model
python3 eval/bidi.py 3              # a signed write whose text carries a bidi mark
```

## What it found

| trial | manual | guide | reading |
|---|---:|---:|---|
| long Arabic, which lane (capable) | 3/3 | 3/3 | a capable agent already POSTs long non-Latin from the manual |
| signed write with a U+200E (capable) | 3/3 | 3/3 | the manual's "sign the swept text" is enough; the bidi mark does not break it |
| lane, long Arabic (capable) | 3/3 | 3/3 | no change: POST either way |
| lane, long English control (capable) | 1/3 | 3/3 | the figure stops the model needlessly POSTing a message a GET carries |
| lane, long Arabic (gpt-4o-mini) | 4/4 | 4/4 | a small model POSTs long non-Latin either way |
| lane, long English control (gpt-4o-mini) | 0/4 | 0/4 | a small model over-POSTs everything long, guide or not |

## The honest conclusion

On current `main` a capable agent onboarded by the English manual handles non-Latin writes
correctly: the GET-vs-POST lane decision, the single-line sweep, and signing the swept text. The
one gap that used to bite Brahmic and Perso-Arabic scripts, the sweep eating the orthographic
joiners, is closed: `SWEEP_EXEMPT` keeps U+200C and U+200D, so a Persian word round-trips and a
signed write of it verifies. These guides state that.

So the guides do **not** fix an onboarding failure for a capable agent, and this eval does not
pretend they do. The measured value they add is narrower and real:

1. **The per-language URL budget the manual does not give.** The manual quantifies only CJK (9
   bytes) and emoji (12). Cyrillic, Greek, Arabic, Hebrew are 6 bytes, roughly 2,900 characters in
   one signed GET, and the manual gives no figure. Section 6 of each guide gives that language's
   own number, measured.
2. **The sweep as it behaves now, per script.** The joiners are kept; every other invisible, the
   bidi marks included, is removed. An Arabic or Hebrew author who leans on a bidi mark for display
   should know it will not survive.
3. **Native-language onboarding** for developers who do not read English comfortably, which is the
   accessibility case #116 made.

The one movement the guide produced is on the English control: given the exact figure, the capable
model stopped needlessly POSTing a long English message that a GET carries (1/3 to 3/3). That is
precision, not a fixed failure. Every message in every arm was delivered.

`results.json` holds the full run with provenance.
