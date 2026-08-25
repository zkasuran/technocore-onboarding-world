#!/usr/bin/env python3
"""Shared eval harness: boot a real instance of the service, ask the gateway model, and
execute the single HTTP request the model describes. No task or scoring lives here; the
individual probes (validate.py, lane.py, bidi.py) own those. Nothing is mocked: a trial runs
against the service's own TestClient with its real MAX_TEXT_CHARS, real clean_text and real
signer, so a trial fails on a decision rather than on byte-wrangling.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAT = Path(os.environ.get("TECHNOCORE_CHAT", ROOT.parent / "technocore-feat"))
GATEWAY = Path(os.environ.get("GATEWAY_ENV", ROOT.parent.parent / ".gateway.env"))
MODEL_OVERRIDE = None


def boot():
    """A real instance of the service: real constants, real clean_text, real signer."""
    root = Path(tempfile.mkdtemp(prefix="eval-"))
    os.environ.update(CHAT_ROOT=str(root), CHAT_RATE_READ="1000000",
                      CHAT_RATE_WRITE="1000000", CHAT_RATE_ROOMS_PER_DAY="1000000")
    sys.path.insert(0, str(CHAT / "src"))
    sys.path.insert(0, str(CHAT / "tests"))
    from starlette.testclient import TestClient
    import app as app_module
    import store
    return TestClient(app_module.app), store, root


def manual(client) -> str:
    """The service's own manual, verbatim, as an onboarding agent reads it."""
    return client.get("/llms.txt").text


def gateway():
    env = {}
    for line in GATEWAY.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env["OPENAI_BASE_URL"], env["OPENAI_API_KEY"], env["OPENAI_MODEL"]


def ask(prompt: str, seed: int) -> str:
    base, key, model = gateway()
    if MODEL_OVERRIDE:
        model = MODEL_OVERRIDE
    body = json.dumps({"model": model, "max_tokens": 3000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body, headers={
        "authorization": f"Bearer {key}", "content-type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as f:
                return json.loads(f.read())["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                return f"__ERROR__ {exc}"
            time.sleep(4 * (attempt + 1))
    return "__ERROR__ unreachable"


def extract_json(text: str) -> dict | None:
    """The request object out of a reply that may carry prose or a fence around it."""
    for chunk in (text, text.replace("```json", "```")):
        if "```" in chunk:
            parts = [p for p in chunk.split("```") if "{" in p]
            if parts:
                chunk = parts[0]
        start, end = chunk.find("{"), chunk.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(chunk[start:end + 1])
            except ValueError:
                continue
    return None


def execute(client, plan, task, did, sign, nonce, store):
    """Substitute the real text, sign if asked, then perform the request.

    The model chooses the lane, the text form and the canonical string; the harness does the
    mechanical encoding so a trial fails on a decision rather than on byte-wrangling.
    """
    text = task["text"]
    if str(plan.get("text_form", "raw")).lower() == "swept":
        text = store.clean_text(text)
    method = str(plan.get("method", "GET")).upper()
    path = str(plan.get("path", ""))
    if not path.startswith("/"):
        path = "/" + path
    signature = ""
    if did is not None:
        template = plan.get("signed_over") or ""
        canonical = (str(template)
                     .replace("{room}", task["room"]).replace("{nonce}", str(nonce))
                     .replace("<room>", task["room"]).replace("<nonce>", str(nonce))
                     .replace("TEXT", text))
        signature = sign(canonical) if canonical else ""
    body = plan.get("body")
    if isinstance(body, dict):
        body = {k: (text if v == "TEXT" else signature if v == "SIG"
                    else str(nonce) if v in ("{nonce}", "<nonce>")
                    else did if v in ("{did}", "<did>") else v) for k, v in body.items()}
    path = (path.replace("SIG", signature).replace("{nonce}", str(nonce))
                .replace("<nonce>", str(nonce)))
    if did:
        path = path.replace("{did}", did).replace("<did>", did)
    path = path.replace("TEXT", urllib.parse.quote(text, safe=""))
    r = client.post(path, json=body or {}) if method == "POST" else client.get(path)
    return r.status_code, r.text, len(path)


def signing_key(seed: int):
    """A throwaway Ed25519 key plus its did:key, so the model can genuinely sign."""
    import base64
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    raw = hashlib.sha256(f"technocore-eval-{seed}".encode()).digest()
    key = Ed25519PrivateKey.from_private_bytes(raw)
    pub = key.public_key().public_bytes_raw()
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    data = b"\xed\x01" + pub
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = alphabet[rem] + out
    did = "did:key:z" + "1" * (len(data) - len(data.lstrip(b"\x00"))) + out

    def sign(message: str) -> str:
        return base64.urlsafe_b64encode(key.sign(message.encode())).decode().rstrip("=")
    return did, sign, raw.hex()


PROMPT = """You are an autonomous agent that has just discovered the service at {base}.
Below is its complete manual, which you have fetched from {base}/llms.txt.

{extra}=== BEGIN {base}/llms.txt ===
{manual}
=== END {base}/llms.txt ===

TASK: {ask}

room: {room}
The message text is {n_chars} characters of {script} script. You do NOT need to reproduce it:
refer to it as the placeholder TEXT and the harness will substitute the real characters
exactly. A sample of the first 40 characters, so you can judge its script and encoding cost:

    {sample}
{creds}
Reply with ONE JSON object and nothing else, describing the single HTTP request you would
send. Use exactly these keys:

{{"method": "GET" or "POST",
  "path": "the path, with the literal token TEXT where the message goes if it goes in the path,
           and any query string. Do not percent-encode TEXT yourself, the harness does that.",
  "body": null, or the JSON object for a POST, using the literal string "TEXT" as the value
          wherever the message goes,
  "text_form": "raw" if the characters should be stored exactly as given, or "swept" if you
               intend the server's single-line sweep to be applied first,
  "signed_over": null if unsigned, else the canonical string you would sign, written as a
                 template using TEXT, {{room}} and {{nonce}} placeholders,
  "why": "one sentence on why you chose this lane"}}

The harness substitutes TEXT, percent-encodes it if it is in the path, computes the signature
over your signed_over template with the given key, and sends the request. So a wrong lane, a
wrong text_form or a wrong canonical string will fail; the exact bytes are not your problem.
Do not explain outside the JSON."""

CREDS = """
This is a signed write. did: {did}
The harness holds the matching private key and will sign whatever canonical string you specify
in signed_over, using nonce {nonce}. Put the signature where the manual says it goes, using the
literal token SIG.
"""
