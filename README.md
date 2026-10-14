# Related Languages Resources (RLR)

**Show translators what already exists in languages next door to theirs.**

RLR is a prototype agentic system, built as part of the Open QA Initiative,
that surfaces Bible
translation resources from *closely-related languages* to translators doing
quality assurance on an in-process translation — and, where possible, renders
those resources in a language the translator actually reads.

Stages 1, 2, 3 and 5 run end to end against live data; stage 4 and the LWC
rendering in stage 5 run once a machine-translation backend is configured and
otherwise report their absence.

---

## Why this exists

A great deal of relevant material already exists for almost any translation
project: completed translations, Paratext Enhanced Resources, Bible Aquifer
resources, translator notes. Often some of it sits in a language closely related
to the target — same family, or a Language of Wider Communication (LWC) used in
the same region.

Translators with limited technology experience largely cannot get to it:

- **Hard to discover** — it lives in external information systems the translator
  has never heard of.
- **Hard to access** — reaching it takes web search and website navigation skills.
- **Hard to read** — even when found, it is often in a language the translator
  does not know.

RLR's job is to collapse all three problems into something that just appears next
to the verse being worked on.

## What it does

Given a translation context — target language, LWC, optionally geographic
location — RLR runs a five-stage pipeline:

| # | Stage | Module | Notes |
|---|-------|--------|-------|
| 1 | Identify closely-related languages | `rlr.languages` | Glottolog classification-path overlap + areal signal, over languages with an eBible text |
| 2 | Narrow to languages with an available Bible | `rlr.catalog` | eBible `licences.tsv`; display vs. derivative rights kept apart |
| 3 | Retrieve the corresponding verse (or pericope) | `rlr.verses` | `vref.txt`-indexed, ranges supported |
| 4 | Back-translate that text into the LWC | `rlr.back_translation` | Via `rlr.mt`; license- and capability-gated |
| 5 | Machine-translate English-only resources into the LWC | `rlr.resources` | unfoldingWord figures of speech via `bible-figures-of-speech` |

Stages 4 and 5 are conditional: if no back-translation or MT capability exists
for the LWC, RLR says so rather than silently returning nothing.

Trust and provenance are a first-class output, not metadata: for each
related-language translation, RLR reports what it is, who produced it and when,
whether it can be trusted, and whether and how it may legally be used.

## Who it is for

Quality assurance personnel:

- A **translator** checking her own or another's output, holding the primary
  knowledge of the target language.
- A **translation consultant or advisor**, with more limited facility in the
  target language but more technical expertise.
- **Community organizations and ministries** reviewing a translation prior to
  publication.

## Jobs to be done

1. **Find translations in closely-related languages** — show me what exists
   without making me find it, so I can judge whether it helps.
2. **Understand translation trust and access** — what is it, who made it, when,
   can I trust it, may I legally use it.
3. **Consult a specific verse in a related language** — while I translate a
   verse, show me the same verse elsewhere, without my knowing how to find it.
4. **Consult a specific verse in an LWC** — same, in a language I read. Tell me
   when there is nothing.
5. **Consult English-only translation resources in an LWC** — find resources for
   this passage that can be auto-translated into an LWC I read. Tell me when
   there is nothing.

Expanded in [`docs/02-jobs-to-be-done.md`](docs/02-jobs-to-be-done.md).

## Clone and play

```bash
git clone git@github.com:TangoGroup/related-languages-resources.git
cd related-languages-resources
./run
```

That installs what is missing (`uv` and the package), starts the demo on
<http://127.0.0.1:8765>, and opens it in your browser. It needs bash, curl and
git on macOS or Linux. `./run help` lists the other commands:

```bash
./run brief ngq swh "MRK 1:3"    # a passage across related languages, in the terminal
./run languages ngq              # the closest languages with Scripture
./run check                      # lint, typecheck, test
```

If you have [`just`](https://github.com/casey/just), the same recipes are in the
`justfile`: `just demo`, `just brief ngq swh "MRK 1:3"`, `just check`,
`just record`.

## Quickstart by hand

```bash
uv sync --extra dev --extra demo
uv run rlr languages --target ngq                       # Ngoreme, Tanzania
uv run rlr brief --target ngq --lwc swh --passage "MRK 1:6"
uv run rlr serve                                        # demo UI on :8765
``` The page shows the passage in each related
language with its provenance and license, the rendering into the LWC or the
reason there is none, the figure-of-speech notes for the passage, and a map of
the related languages placed by their Glottolog coordinates.

The first run downloads Glottolog's CLDF export and the eBible metadata
(about 35 MB) into `~/.cache/rlr`; corpus texts are fetched per edition on
demand. Everything after that is offline.

Environment variables:

| Variable | Purpose |
|---|---|
| `RLR_CACHE_DIR` | Download cache (default `~/.cache/rlr`) |
| `RLR_FIGURES_DIR` | Optional alternative snapshot of the figures-of-speech data (`figs_types.yaml` plus `figs_instances/`). Unset, the copy bundled in `bible-figures-of-speech` is used |
| `RLR_MT` | Live machine-translation backend: `none` (default) or `madlad[:model-id]`; needs `uv sync --extra mt`. Pre-rendered notes work without it |
| `RLR_MT_DEVICE` | Force `cuda`, `mps` or `cpu` for the live backend; unset picks the best available |
| `RLR_RENDERINGS_DIR` | Extra directory of pre-rendered translations (`<lwc>.json.gz`), searched before the cache and the bundled copies |
| `RLR_LWC_CSV` | Optional `lwc.csv` (per-language LWC probabilities) to suggest LWCs |
| `RLR_OFFLINE` | Set to fail instead of downloading |

Extras: `demo` (FastAPI + uvicorn for `rlr serve`), `mt` (MADLAD-400 via transformers).

**Pre-rendered notes.** The figures-of-speech notes for the Gospels of Mark,
Luke and John come with the package already rendered into Swahili, Indonesian
and Portuguese (`src/rlr/data/renderings/<lwc>.json.gz`, produced once with
MADLAD-400), so the demo shows notes in those languages with no model
installed. Renderings are looked up before any live backend, so this works
with the default `RLR_MT=none`.

**Live machine translation.** For other passages or languages, run the model
in-process; there is no server:

```bash
RLR_MT=madlad ./run    # installs torch and transformers, downloads the 11 GB model, starts the demo
```

Stages 4 and 5 then render into any language MADLAD-400 covers (some 400);
related languages it was not trained on are reported as unavailable rather
than guessed. It uses an NVIDIA GPU or Apple silicon when present and the CPU
otherwise; budget about 6 GB of memory and, on a CPU, a few seconds per
sentence, so a verse with three notes takes about a minute the first time.

**Extending the pre-rendered set.** `rlr pretranslate --lwc ind --book ROM`
renders a book's notes once with the live backend into your cache
(`~/.cache/rlr/renderings`); `--bundle` writes into the package data
instead, for shipping. `RLR_RENDERINGS_DIR` adds another directory to search
first.

A narrated walkthrough of the demo UI can be re-recorded with
`demo/record.py`: it drives the running server with Playwright, narrates each
scene with ElevenLabs (key in `~/.config/elevenlabs.key`), and muxes the result
into `demo/out/rlr-demo.mp4` with ffmpeg. Scenes and script live in
`demo/narration.py`.

## How it works

Full detail in [`docs/03-architecture.md`](docs/03-architecture.md); source
survey in [`docs/04-data-sources.md`](docs/04-data-sources.md).

**Identifying related languages.** Glottolog's classification is read from its
CLDF export (two CSV files, no clone of the 1 GB repository) and cached as JSON.
Two languages score by the overlap of their classification paths (after Sean
Boisen's language-similarity measure), with a flat areal score for
cross-family neighbours that share a country. The
candidate set is the languages that have a text in the eBible Corpus, so stages
1 and 2 answer one question between them. For Ngoreme (`ngq`) the top eBible
relatives are Suba 0.85, Kara 0.83, Isanzu and Pogolo 0.78, Ganda 0.75.

**Finding and retrieving Bibles.** The **eBible Corpus** has 1079 texts,
one-verse-per-line, aligned to a canonical verse list in `vref.txt`, with a
license per text in `licences.tsv`. Three quarters of the licensed texts forbid
derivatives: those are shown verbatim in stage 3 and refused, with the license
named, in stages 4 and 5. Texts are downloaded once per edition and cached.

**Rendering into the LWC.** `rlr.mt` defines a small machine-translation
backend protocol; the default backend supports nothing, so every LWC
rendering is reported as unavailable with a reason until a backend is
configured. MADLAD-400 runs locally through the `mt` extra; other backends
plug in behind the same protocol.

**English-only resources.** unfoldingWord's figures-of-speech notes, shipped
in the [`bible-figures-of-speech`](https://pypi.org/project/bible-figures-of-speech/)
package (CC BY-SA 4.0 data), are joined to their
type, matched to the passage, and rendered into the LWC through the same
backend. Many other verse-indexed datasets could ride the same path.

**The agent.** `Pipeline.brief` composes the stages into a briefing where every
text carries its source, producer, date and license, and every gap carries a
reason. No language model sits on the request path.

## Evaluation

1. Are related languages successfully identified?
2. Where open translations exist for related languages, is their content retrieved?
3. Is the *correct* related-language Bible text retrieved for a target verse?
4. Is that text successfully back-translated into the LWC? *(qualitative — both
   whether the back-translation is correct and whether the result is useful)*
5. Where figure-of-speech data exists for a target verse, is it retrieved?
6. Is that data successfully translated? *(qualitative)*

## Design and limitations

The constraints behind the code (trust as an output, absence as a result,
separate display and derivative rights, pluggable machine translation) are in
[`docs/05-design-rationale.md`](docs/05-design-rationale.md). Known
limitations, among them unevaluated relatedness, sparse open coverage for some
languages, and MT drift toward memorised scripture, are in
[`docs/07-limitations-and-future-work.md`](docs/07-limitations-and-future-work.md).

## Development

```bash
git clone git@github.com:TangoGroup/related-languages-resources.git
cd related-languages-resources
uv sync --extra dev --extra demo   # one-time: install
uv run pre-commit install          # one-time: enable commit hooks
uv run pytest                      # offline suite, fixtures under tests/fixtures
uv run ruff check .                # lint
uv run mypy                        # typecheck (strict)
```

## Repository layout

```
docs/                 the specification, in eight numbered documents
src/rlr/
  types.py            core domain types (PassageRef, Provenance, LicenseClass, ...)
  config.py           settings from RLR_* variables; the download cache
  glottolog.py        Glottolog CLDF loader and path-overlap similarity
  ebible.py           eBible Corpus metadata, licenses, corpus files
  languages.py        stage 1 — related-language identification
  catalog.py          stage 2 — which related languages have usable Bibles
  verses.py           stage 3 — verse/pericope retrieval from the corpus
  mt.py               Translator protocol and backends (none, MADLAD-400, pre-rendered)
  renderings.py       pre-rendered translations: file format, cache, batch renderer
  data/renderings/    notes for the Gospels rendered into Swahili, Indonesian, Portuguese
  back_translation.py stage 4 — rendering into the LWC
  resources/          stage 5 — English-only verse-indexed resources
  agent.py            the pipeline that hides all of the above
  cli.py              `rlr` command-line entry point (brief, languages, serve)
  demo/               FastAPI demo UI: server.py + static/
tests/                offline; fixtures under tests/fixtures
```

## Documentation

- [`AGENTS.md`](AGENTS.md) — orientation for coding agents; start a coding session here
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — setup, working agreements, extension points
- [`docs/01-context-and-goals.md`](docs/01-context-and-goals.md)
- [`docs/02-jobs-to-be-done.md`](docs/02-jobs-to-be-done.md)
- [`docs/03-architecture.md`](docs/03-architecture.md)
- [`docs/04-data-sources.md`](docs/04-data-sources.md)
- [`docs/05-design-rationale.md`](docs/05-design-rationale.md)
- [`docs/06-evaluation.md`](docs/06-evaluation.md)
- [`docs/07-limitations-and-future-work.md`](docs/07-limitations-and-future-work.md)
- [`docs/08-dependencies-and-licenses.md`](docs/08-dependencies-and-licenses.md)

## License

MIT. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Third-party corpora
and the `bible-figures-of-speech` data (CC BY-SA 4.0) carry their own licenses;
RLR's own license does not extend to them. Every dependency and data source,
with its license, is listed in
[`docs/08-dependencies-and-licenses.md`](docs/08-dependencies-and-licenses.md).
Contributions are welcome; see [`CONTRIBUTING.md`](CONTRIBUTING.md).
