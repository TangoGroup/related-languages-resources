# 4. Data sources

## Summary

| Source | Coverage | Access | Verdict |
|---|---|---|---|
| **eBible Corpus** | 1079 texts, `licences.tsv` per text | Plain text, verse-per-line | **Working choice**, also the license source |
| Open.Bible | 945 openly-licensed Bibles | Free re-use, various formats | Not needed; eBible carries its own licenses |
| Digital Bible Library (DBL) | Primary repository, all types | License agreements required | Blocked for prototype |
| API.Bible | Access layer over DBL | Paid account; no derivative works | Rejected |
| YouVersion Platform | Large | ToS **forbids AI usage**; word-for-word retrieval only | Rejected |
| Bible Brain (FCBH) | Audio + text | API | Future — audio track |
| Scripture Forge | Back-translations, ~200 languages | Paratext creds + SIL NLP access | Stage 4, with caveats |
| unfoldingWord translation notes | Figures of speech | CC BY-SA 4.0, YAML | Stage 5 dataset |

## Bible text

**Open.Bible** lists Bibles that are freely available for re-use, in a variety
of formats. Note the worked example: *none of the languages closely related to
Biafada have an openly-available Bible.* This is the sharp edge of open question
[Q1](06-open-questions.md).

**Digital Bible Library** is the primary repository for all types of Bibles. It
includes Bibles in Wamey, Gola and Serer — but none are available without
license agreements.

**API.Bible** exists to help with accessing content, but requires a paid account
and does not allow derivative works. Back-translation and machine translation are
derivative works, so this rules it out for RLR's core function, not merely
inconveniences it.

**YouVersion Platform** offers an API, but the Terms of Service explicitly forbid
AI usage and allow only word-for-word accurate retrieval. Rejected.

**Bible Brain / Faith Comes By Hearing** provides an API for retrieving audio and
text. Relevant mainly to the audio idea in
[08-future-work.md](08-future-work.md).

**eBible Corpus** has 1079 Bible texts, parsed into a standard verse-oriented
format with plain text, one verse per line, aligned to `vref.txt`
([03-architecture.md](03-architecture.md) §Stage 3). Its `metadata/licences.tsv`
gives the license per text:

| Licence type | Texts | `LicenseClass` |
|---|---|---|
| by-nc-nd | 708 | derivatives forbidden |
| Unknown | 255 | unknown (not shown) |
| by-sa | 124 | open |
| by-nd | 106 | derivatives forbidden |
| Public Domain | 99 | open |
| by | 40 | open |
| by-nc | 3 | non-commercial |

Three quarters of the licensed texts forbid derivatives. Those are displayed in
stage 3 and refused in stages 4 and 5, with the reason stated (D8).

**Coverage that matters for the demo.** Tanzania has 21 texts, 9 of them
derivative-friendly (Isanzu, Kisi, Ndengereko, Pogolo, Kara, Safwa, Vwanji,
Kinga, Swahili), which is why the demo case is Tanzanian with Swahili as LWC
(D9). For Biafada, Wamey, Gola, Mansoanka and Serer are absent; five Fulfulde
varieties are present, all no-derivatives; Kriol (`pov`) is absent.

## Back-translations

**Scripture Forge** — back translations for about 200 languages. See
[Understanding Draft Generation | Scripture Forge Help](https://help.scriptureforge.org/).
Requires Paratext credentials plus access granted by the SIL Natural Language
Processing team. Draft generation takes ~90 minutes or longer, so it is a setup
step rather than a request-path call.

Known practical risk: this process has historically been "very white glove", and
it is unclear whether that has changed. Treat availability as unproven until
demonstrated — see [06-open-questions.md](06-open-questions.md) §Q2.

## Verse-indexed English resources

**unfoldingWord translation notes → figures of speech**, reorganized as YAML
by Sean Boisen and published on PyPI as
[`bible-figures-of-speech`](https://pypi.org/project/bible-figures-of-speech/)
(MIT code, CC BY-SA 4.0 data, snapshot 2026-09-16):

- `figs_instances/<NN>-<USFM>.yaml` — 56 books, instances with `ref`,
  `type_id`, source text, gloss, comment and alternate translations
- `figs_types.yaml` — 19 figure-of-speech types with descriptions and links

The same content is public on Door43 as `unfoldingWord/en_tn` (TSV with
`SupportReference` = `figs-*`) and `en_ta/translate/figs-*`, CC BY-SA 4.0, if a
loader for the original layout is ever needed.

The shape generalizes: any verse-indexed dataset can be delivered the same way,
so treat the figures-of-speech loader as one implementation of an interface, not
a special case.

## Language data

**Glottolog** classification, read from the CLDF export
[`glottolog/glottolog-cldf`](https://github.com/glottolog/glottolog-cldf)
(`languages.csv` 2.4 MB, `values.csv` 21 MB; CC BY 4.0) and cached as JSON.
Scoring is a classification-path overlap (Sean Boisen's in-house measure); an
optional `lwc.csv` (derived from Glottolog country data and Unicode CLDR
territory language shares) can suggest LWCs. A nearest-supported-language
search over the same tree answers a different question and is not used. See
[03-architecture.md](03-architecture.md) §Stage 1.

## Machine translation

In house (D10). The first concrete backend is **MADLAD-400**
(`google/madlad400-3b-mt`, Apache-2.0), which covers English → Swahili and
most LWCs. Its training data includes a Swahili Bible, which biases
back-translation of scripture (Q5). Other in-house models plug in behind the
same `Translator` protocol.

## Licensing posture

RLR's code is MIT-licensed. **None of the corpora above inherit that license.** Any
caching, redistribution or derivative generation must be checked per source.
The per-translation license is itself a user-facing output
([02-jobs-to-be-done.md](02-jobs-to-be-done.md) §2.2), so license data must be
carried through the pipeline rather than discarded after filtering.
