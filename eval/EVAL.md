# The eval

Issue [#116](https://github.com/flop-labs/technocore-chat/issues/116) proposed a translated
onboarding guide and was closed with one ask: *"Is there an example where current guide for
agents is not followed/understood by agent? Please reopen with eval example where it improves
onboarding."* This is that eval; it reports what it found rather than what would help the
case.

## How a trial works

Every trial runs against a real instance of the service booted from its own source: its own
`TestClient`, the real `MAX_TEXT_CHARS`, the real `clean_text`, the real signer. No mocks. The
model is handed the service's own `/llms.txt` verbatim, which is what an agent onboarding today
actually reads, then asked to perform a task. It replies with one JSON object describing a single
HTTP request. The harness substitutes the real text, signs if asked, sends it and scores the
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
correctly: the GET-vs-POST lane decision, the single-line sweep and signing the swept text. The
sweep removes every invisible, the orthographic joiners U+200C/U+200D included, so a Perso-Arabic
or Brahmic word is stored with its joiner gone and a signature over the raw text 403s. The manual
says to sign the swept text and a capable agent does, so the write still lands; the stored spelling
differs, which these guides document. (Our PR #158 proposes keeping the two joiners.)

So the guides do **not** fix an onboarding failure for a capable agent; this eval does not
pretend they do. The measured value they add is narrower and real:

1. **The per-language URL budget the manual does not give.** The manual quantifies only CJK (9
   bytes) and emoji (12). Cyrillic, Greek, Arabic, Hebrew are 6 bytes, roughly 2,900 characters in
   one signed GET; the manual gives no figure. Section 6 of each guide gives that language's
   own number, measured.
2. **The sweep, per script.** Every invisible is replaced with a space, the orthographic joiners
   U+200C/U+200D and the bidi marks alike, so a Perso-Arabic or Brahmic word is altered and a signed
   write over the raw text 403s. Each guide names the exact character for its script.
3. **Native-language onboarding** for developers who do not read English comfortably, which is the
   accessibility case #116 made.

The one movement the guide produced is on the English control: given the exact figure, the capable
model stopped needlessly POSTing a long English message that a GET carries (1/3 to 3/3). That is
precision, not a fixed failure. Every message in every arm was delivered.

`results.json` holds the full run with provenance.
