#!/usr/bin/env python3
"""Measure every per-language number the world onboarding pack states, against the service's
own code rather than a description of it. Nothing here is hand-typed.

Two things get measured per language, on upstream `main`:

  URL BUDGET. `MAX_TEXT_CHARS` is a CHARACTER cap; the GET write lane carries the text in the
  URL path, so its real limit is URL length (~16 KB at the edge). One ASCII character is 1 URL
  byte, a 2-byte script (Cyrillic, Greek, Arabic, Hebrew) is 6, a 3-byte script (CJK, Thai,
  and Vietnamese's precomposed vowels) is 9, an emoji 12. So "how many characters fit one GET"
  is per script, and the manual quantifies only CJK. Every number below is measured.

  THE SWEEP. `clean_text` replaces every character in Cc/Cf/Cs/Co/Zl/Zp with a space. On the
  deployed service (0.9.2) that includes the orthographic joiners U+200C/U+200D, so a Persian
  word spelled with a ZWNJ is stored altered and a signed write over the pre-sweep text 403s.
  Bidi marks (U+200E/200F/061C and the isolates) are removed the same way. An open change, PR
  #158, would hold the two joiners out; this script reports whatever the target it measures
  actually does, joiner and bidi samples round-tripped through the real `clean_text`.

Run:  python3 measure.py            # writes measured.json and prints the table
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHAT = Path(os.environ.get("TECHNOCORE_CHAT", ROOT.parent.parent / "technocore-feat"))
sys.path.insert(0, str(CHAT / "src"))
import store  # noqa: E402

# Major world languages by speakers and by agent-developer population, across eight scripts.
# `sample` is a plain greeting in the script the language is actually written in. `joiner` is a
# real word that needs ZWNJ/ZWJ (only Persian here); it should now SURVIVE the sweep. `bidi` is
# a right-to-left fragment with an embedded bidi mark (U+200E LRM); it should be ALTERED.
LANGUAGES = [
    # code      name                    endonym            script     sample               joiner    bidi
    ("en",      "English",              "English",         "Latin",   "hello world",        "",       ""),
    ("es",      "Spanish",              "Español",         "Latin",   "Hola mundo",         "",       ""),
    ("fr",      "French",               "Français",        "Latin",   "Bonjour le monde",   "",       ""),
    ("de",      "German",               "Deutsch",         "Latin",   "Hallo Welt",         "",       ""),
    ("pt",      "Portuguese",           "Português",       "Latin",   "Olá mundo",          "",       ""),
    ("it",      "Italian",              "Italiano",        "Latin",   "Ciao mondo",         "",       ""),
    ("id",      "Indonesian",           "Bahasa Indonesia","Latin",   "Halo dunia",         "",       ""),
    ("tr",      "Turkish",              "Türkçe",          "Latin",   "Merhaba dünya",      "",       ""),
    ("pl",      "Polish",               "Polski",          "Latin",   "Witaj świecie",      "",       ""),
    ("vi",      "Vietnamese",           "Tiếng Việt",      "Latin",   "Xin chào thế giới",  "",       ""),
    ("ru",      "Russian",              "Русский",         "Cyrillic","Привет мир",         "",       ""),
    ("el",      "Greek",                "Ελληνικά",        "Greek",   "Γειά σου κόσμε",     "",       ""),
    ("ar",      "Arabic",               "العربية",         "Arabic",  "مرحبا بالعالم",      "",       "غزة‎ 2024"),
    ("fa",      "Persian",              "فارسی",           "Arabic",  "سلام دنیا",          "می‌روم", "نسخه‎ 3.2"),
    ("he",      "Hebrew",               "עברית",           "Hebrew",  "שלום עולם",          "",       "גרסה‎ 3.2"),
    ("zh-Hans", "Chinese (Simplified)", "简体中文",          "Han",     "你好世界",            "",       ""),
    ("zh-Hant", "Chinese (Traditional)","繁體中文",          "Han",     "你好世界",            "",       ""),
    ("ja",      "Japanese",             "日本語",           "Japanese","こんにちは世界",       "",       ""),
    ("ko",      "Korean",               "한국어",           "Hangul",  "안녕하세요 세계",       "",       ""),
    ("th",      "Thai",                 "ไทย",             "Thai",    "สวัสดีชาวโลก",        "",       ""),
]

# The signed GET lane spends its path on credentials before <text>: a did:key is 56 characters,
# an Ed25519 signature 86 base64url, a millisecond nonce 13.
SIGNED_PREFIX = len("/r/") + 48 + len("/say-signed/") + 56 + 1 + 86 + 1 + 13 + 1
UNSIGNED_PREFIX = len("/r/") + 48 + len("/say/") + 48 + 1
EDGE_URL_LIMIT = 16 * 1024


def witness(sample: str) -> dict:
    """What actually happens to `sample` when it passes through the real `clean_text`."""
    swept = store.clean_text(sample)
    invis = [f"U+{ord(c):04X} {unicodedata.category(c)}"
             for c in sample if unicodedata.category(c) in store.INVISIBLE_CATEGORIES]
    return {"text": sample, "invisibles": invis, "stored_as": swept, "survives": swept == sample}


def measure_one(code, name, endonym, script, sample, joiner, bidi) -> dict:
    encoded = urllib.parse.quote(sample, safe="")
    per_char = len(encoded) / len(sample)
    row = {
        "code": code, "language": name, "endonym": endonym, "script": script, "sample": sample,
        "sample_chars": len(sample),
        "sample_url_bytes": len(encoded),
        "url_bytes_per_char": round(per_char, 2),
        "chars_in_unsigned_get": int((EDGE_URL_LIMIT - UNSIGNED_PREFIX) / per_char),
        "chars_in_signed_get": int((EDGE_URL_LIMIT - SIGNED_PREFIX) / per_char),
        "max_text_chars_url_bytes": int(store.MAX_TEXT_CHARS * per_char),
        # Is the documented character cap even reachable by GET in this script, or does the URL
        # edge bite first? True means a full-length message must use POST.
        "post_required_at_cap": int(store.MAX_TEXT_CHARS * per_char) + SIGNED_PREFIX > EDGE_URL_LIMIT,
        # The character count past which even a mid-length message cannot go by signed GET.
        "signed_get_ceiling_chars": int((EDGE_URL_LIMIT - SIGNED_PREFIX) / per_char),
    }
    if joiner:
        # Should now SURVIVE: SWEEP_EXEMPT holds U+200C/U+200D on current main.
        row["joiner"] = witness(joiner)
    if bidi:
        # Should be ALTERED: bidi marks are Cf and not exempt, so the sweep removes them.
        row["bidi"] = witness(bidi)
    return row


def main():
    rows = [measure_one(*entry) for entry in LANGUAGES]

    def _rev():
        try:
            return subprocess.check_output(
                ["git", "-C", str(CHAT), "rev-parse", "--short", "HEAD"], text=True).strip()
        except Exception:  # noqa: BLE001
            return "unknown"

    def _version():
        try:
            for line in (CHAT / "pyproject.toml").read_text().splitlines():
                if line.strip().startswith("version"):
                    return line.split('"')[1]
        except Exception:  # noqa: BLE001
            pass
        return "unknown"

    out = {
        "measured_against": "src/store.py of flop-labs/technocore-chat at upstream main",
        "measured_commit": _rev(),
        "service_version": _version(),
        "constants": {
            "MAX_TEXT_CHARS": store.MAX_TEXT_CHARS,
            "MAX_VALUE_CHARS": store.MAX_VALUE_CHARS,
            "INVISIBLE_CATEGORIES": list(store.INVISIBLE_CATEGORIES),
            "sweep_exempt": [f"U+{ord(c):04X}" for c in sorted(getattr(store, "SWEEP_EXEMPT", frozenset()))],
            "edge_url_limit_bytes": EDGE_URL_LIMIT,
            "signed_get_prefix_bytes": SIGNED_PREFIX,
            "unsigned_get_prefix_bytes": UNSIGNED_PREFIX,
        },
        "languages": rows,
    }
    (ROOT / "measured.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8")

    print(f"{'lang':22} {'code':8} {'script':10} {'B/ch':>5} {'GET':>7} {'signed':>7} "
          f"{'POST@cap':>9} {'joiner':>8} {'bidi':>6}")
    for r in rows:
        j = r.get("joiner")
        b = r.get("bidi")
        jt = "-" if not j else ("kept" if j["survives"] else "LOST")
        bt = "-" if not b else ("kept" if b["survives"] else "stripped")
        print(f"{r['language']:22} {r['code']:8} {r['script']:10} {r['url_bytes_per_char']:5.2f} "
              f"{r['chars_in_unsigned_get']:7} {r['chars_in_signed_get']:7} "
              f"{('yes' if r['post_required_at_cap'] else 'no'):>9} {jt:>8} {bt:>6}")
    print(f"\nMAX_TEXT_CHARS = {store.MAX_TEXT_CHARS} characters; SWEEP_EXEMPT = "
          f"{[f'U+{ord(c):04X}' for c in sorted(getattr(store, 'SWEEP_EXEMPT', frozenset()))] or 'none (all invisibles swept)'}")
    print(f"wrote {ROOT / 'measured.json'}")


if __name__ == "__main__":
    main()
