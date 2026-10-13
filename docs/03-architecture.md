# 3. Architecture

We anticipate prototyping an **agentic AI architecture** that hides the
underlying infrastructure and simply exposes information that is relevant to and
understandable by the user. **Providing trusted information is a high priority.**

The translator should never see a source catalogue, a license negotiation, or a
versification rule. They should see verses and notes they can read.

## Pipeline

```
translation context                                          translator
(target lang, LWC, [location], verse ref)                         ^
        |                                                         |
        v                                                         |
  [1] related languages  ->  [2] which have usable Bibles         |
                                      |                           |
                                      v                           |
                             [3] verse / pericope text  ------>  [4] back-translated to LWC
                                                                  |
        [5] English-only verse-indexed resources  --------------->+  (machine-translated to LWC)
```

Stages 4 and 5 are conditional on capability existing for the LWC. When it does
not, the system reports the absence explicitly (see
[02-jobs-to-be-done.md](02-jobs-to-be-done.md) §2.4, §2.5).

## Stage 1 — Identifying related languages

`src/rlr/languages.py`, data in `src/rlr/glottolog.py`

Two in-house measures over Glottolog's tree were candidates:

- A nearest-supported-language search (Joshua Nemecek) walks the tree to find,
  for each language, the closest language that a given speech model supports.
  The worked Biafada example in the design doc comes from it: Wamey, Fulah,
  Gola, Mansoanka and Serer are the supported entries at distance 4. That is
  the right question for speech tooling; RLR's target set is different.
- A classification-path overlap (Sean Boisen) scores every pair of Glottolog
  languages by the overlap of their classification paths, plus a flat areal
  score for cross-family pairs that share a country.

RLR uses the second measure (decision D7), computed in-repo over Glottolog's
CLDF export (`languages.csv` and the `classification` parameter in
`values.csv`), so no Glottolog clone is needed. The candidate set is the
languages that have a text in the eBible Corpus, which means stages 1 and 2
answer one question between them. A known caveat: neither measure is
strongly geographic. Glottolog coordinates give a distance that is reported
alongside the score, and an optional LWC table (probability that a speaker of
A also speaks LWC B) is exposed through `rlr.languages.suggest_lwcs` when an
`lwc.csv` is available.

Quality is unevaluated (Q4). For Ngoreme (`ngq`) the top eBible relatives are
Suba 0.85, Kara 0.83, Isanzu and Pogolo 0.78, Ganda 0.75.

## Stage 2 — Finding Bibles in related languages

`src/rlr/catalog.py`

The working choice is the **eBible Corpus**, whose `licences.tsv` supplies the
license per translation (`src/rlr/ebible.py`). Licenses map onto
`LicenseClass`; `DISPLAYABLE` (open, non-commercial, no-derivatives) governs
stage 3 and `DERIVABLE` (open, non-commercial) governs stages 4 and 5. Full
source survey in [04-data-sources.md](04-data-sources.md).

## Stage 3 — Retrieving verse text in related languages

`src/rlr/verses.py`

Assuming a Bible's text has a license that allows open access, retrieving the
text of a verse should be straightforward. With the eBible Corpus, the line
number provides an index to the verse, with adjustments for versification in
some cases.

> Each Bible is presented in a verse-per-line format. The sequence of the verses
> in each Bible is aligned to a canonical list of Biblical books, chapters, and
> verses. This canonical verse list is based on the Original versification, and
> the verse reference list can be found in the file `vref.txt`. The verse
> reference and verse text for a Bible can be correlated by iterating in
> parallel through the lines of the `vref.txt` file and the lines of a Bible.

Since a given translation effort is only likely to be interested in a small
number of Bibles in related languages, the available translations can be
downloaded initially and then cached for efficient retrieval.

Extraction has already normalised every edition to the Original
versification, so a line number is a verse. Blank lines are missing verses;
`<range>` marks verses folded into the previous line. Multi-verse
`PassageRef`s work; what is missing for pericopes is a dataset to choose
ranges from ([05-decisions.md](05-decisions.md) §D3).

## Stage 4 — Back-translation into the LWC

`src/rlr/back_translation.py`, backends in `src/rlr/mt.py`

Where translators understand the LWC better than the related language, a back
translation from the related language's Bible text into the LWC may be more
helpful than the raw text. It runs only when the LWC has no open Bible of its own: when it does, that
text leads the briefing and nothing is machine-translated (GAI-10145). Otherwise
three gates apply, in order: the source license must permit derivatives; a
backend must support the language pair; and the result is labelled as machine
output with the backend named in its provenance.

Machine translation is in house (decision D10). `rlr.mt.Translator` is a small
protocol; `NoTranslator` is the default and supports nothing, so absence is
reported. `MadladTranslator` runs MADLAD-400 through `transformers` (the `mt`
extra) with the `<2xx>` target tag. One caution: MADLAD has a Swahili Bible in
its training data, so on scripture it drifts toward that text rather than the
source. Stage 4 output is a reading aid, not a literal back-translation, until
Q5 is settled.

**Scripture Forge** drafting is backed by the Serval REST API, which has public
pretranslation endpoints. Access needs Paratext credentials plus SIL NLP team
approval (Q2); draft generation takes about ninety minutes, so it would be a
setup-time comparison, not a request-path dependency (D5).

## Stage 5 — Machine translation of English content into the LWC

`src/rlr/resources/`

Other translation content may only be available in English or another major
language. For this prototype we use the **figure of speech** data from
unfoldingWord's translation notes as the example dataset. This is an important
translation use case, and it is data that is not available for most languages.
Many other datasets with verse-level information could be delivered and accessed
in the same format.

The unfoldingWord data, reorganised into YAML by Sean Boisen and published as
the [`bible-figures-of-speech`](https://pypi.org/project/bible-figures-of-speech/)
package (snapshot 2026-09-16), has two parts:

- `figs_types.yaml` — 19 figure types with label, summary, verbatim
  description and translation issue, examples, and the translationAcademy URL.
- `figs_instances/<NN>-<USFM>.yaml` — 56 books of instances: `ref` (single
  verse or a range like `ROM 3:1-ROM 3:9`), `type_id`, source-language text,
  English gloss, the note's comment and its alternate translations.

`rlr.resources.figures_of_speech.FiguresOfSpeech` wraps the package's loader
(bundled data, or `RLR_FIGURES_DIR` for another snapshot) and returns notes whose
reference overlaps the passage. The agent renders each note into the LWC through
the same `Translator` as stage 4, or reports absence. Content is unfoldingWord's,
CC BY-SA 4.0, and every note carries that provenance.

## The agent layer

`src/rlr/agent.py`

The agent is what the translator interacts with. `Pipeline.brief` composes the
five stages into a `Briefing`: related languages, one reading per edition
(original text plus its LWC rendering or an `Unavailable`), verse-indexed notes
(original plus rendering or `Unavailable`), and explicit reasons for everything
skipped. It is where the "trusted information is a high priority" requirement is
enforced: nothing is presented without its source, producer, date and license.

Composition is deterministic; no language model sits on the request path. The
jobs are retrieval and rendering, and trust is easier to demonstrate when every
string shown traces to a file and a line. The CLI (`rlr brief`, `rlr
languages`) is the development surface. `rlr serve` runs the demo UI
(`src/rlr/demo`): a FastAPI app exposing `/api/brief` and `/api/languages`
over the same `Pipeline`, and a static page that renders readings, provenance,
license badges, LWC renderings or their absence, the notes, and a map of the
related languages from Glottolog coordinates.
