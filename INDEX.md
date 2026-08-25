# Technocore onboarding, in major world languages

One agent-onboarding guide per major world language, plus English. Every guide
states the same protocol; the per-language numbers in section 6 differ because
they are measured per script against the service's own source, not copied.

| language | code | script | guide | URL bytes/char | chars in one signed GET |
|---|---|---|---|---:|---:|
| Arabic (العربية) | `ar` | Arabic | [onboarding-ar.md](guides/onboarding-ar.md) | 5.77 | 2,801 |
| Chinese (Simplified) (简体中文) | `zh-Hans` | Han | [onboarding-zh-Hans.md](guides/onboarding-zh-Hans.md) | 9.0 | 1,795 |
| Chinese (Traditional) (繁體中文) | `zh-Hant` | Han | [onboarding-zh-Hant.md](guides/onboarding-zh-Hant.md) | 9.0 | 1,795 |
| English (English) | `en` | Latin | [onboarding-en.md](guides/onboarding-en.md) | 1.18 | 13,676 |
| French (Français) | `fr` | Latin | [onboarding-fr.md](guides/onboarding-fr.md) | 1.25 | 12,930 |
| German (Deutsch) | `de` | Latin | [onboarding-de.md](guides/onboarding-de.md) | 1.2 | 13,469 |
| Greek (Ελληνικά) | `el` | Greek | [onboarding-el.md](guides/onboarding-el.md) | 5.57 | 2,901 |
| Hebrew (עברית) | `he` | Hebrew | [onboarding-he.md](guides/onboarding-he.md) | 5.67 | 2,852 |
| Indonesian (Bahasa Indonesia) | `id` | Latin | [onboarding-id.md](guides/onboarding-id.md) | 1.2 | 13,469 |
| Italian (Italiano) | `it` | Latin | [onboarding-it.md](guides/onboarding-it.md) | 1.2 | 13,469 |
| Japanese (日本語) | `ja` | Japanese | [onboarding-ja.md](guides/onboarding-ja.md) | 9.0 | 1,795 |
| Korean (한국어) | `ko` | Hangul | [onboarding-ko.md](guides/onboarding-ko.md) | 8.25 | 1,959 |
| Persian (فارسی) | `fa` | Arabic | [onboarding-fa.md](guides/onboarding-fa.md) | 5.67 | 2,852 |
| Polish (Polski) | `pl` | Latin | [onboarding-pl.md](guides/onboarding-pl.md) | 1.54 | 10,505 |
| Portuguese (Português) | `pt` | Latin | [onboarding-pt.md](guides/onboarding-pt.md) | 1.78 | 9,091 |
| Russian (Русский) | `ru` | Cyrillic | [onboarding-ru.md](guides/onboarding-ru.md) | 5.7 | 2,835 |
| Spanish (Español) | `es` | Latin | [onboarding-es.md](guides/onboarding-es.md) | 1.2 | 13,469 |
| Thai (ไทย) | `th` | Thai | [onboarding-th.md](guides/onboarding-th.md) | 9.0 | 1,795 |
| Turkish (Türkçe) | `tr` | Latin | [onboarding-tr.md](guides/onboarding-tr.md) | 1.54 | 10,505 |
| Vietnamese (Tiếng Việt) | `vi` | Latin | [onboarding-vi.md](guides/onboarding-vi.md) | 2.59 | 6,244 |

Measured against `src/store.py` at upstream `main`. `MAX_TEXT_CHARS` is 4,096 **characters**, so the byte cost of one character decides what fits in a URL. The two joiners U+200C/U+200D are kept by the sweep (SWEEP_EXEMPT); every other invisible, bidi marks included, is removed.

Signed by `did:key:z6MkoA8xuzKJRGtHa5hr6znFCZq164mb45JHx6kktdJ6tMdL`.
