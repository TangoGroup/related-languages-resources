# AGENTS.md

Orientation for coding agents (Claude Code, Codex, Cursor and the like) and
the people driving them. Humans should start with the [README](README.md);
[CONTRIBUTING.md](CONTRIBUTING.md) has the contribution process.

## What this is

**Related Languages Resources (RLR)** is a prototype from the Open QA
Initiative. Given a translation context, it surfaces Bible translation
resources from closely-related languages to translators doing quality
assurance on an in-process translation, rendered where possible into a
Language of Wider Communication (LWC) the translator reads.

Stages 1, 2, 3 and 5 run against live data. Stage 4 and LWC rendering sit
behind a pluggable machine-translation backend that defaults to "none" and
reports its absence. Tests are offline, against fixtures under
`tests/fixtures`.

## The pipeline

Given a translation context (target language, LWC, optional location) and a
passage:

1. **`rlr.languages`**: identify closely-related languages by Glottolog
   classification-path overlap plus an areal score for shared countries,
   computed over the languages that have an eBible text. Reads Glottolog's
   CLDF export via `rlr.glottolog`.
2. **`rlr.catalog`**: keep those with a usably-licensed Bible. eBible's
   `licences.tsv` is the license source (`rlr.ebible`). No-derivatives texts
   may be displayed but not rendered; `DISPLAYABLE` and `DERIVABLE` in
   `rlr.types` encode the two rights.
3. **`rlr.verses`**: retrieve the passage (`vref.txt`-indexed,
   verse-per-line, `<range>` markers and blank verses handled; multi-verse
   passages work).
4. **`rlr.back_translation`**: render into the LWC through an
   `rlr.mt.Translator`. The default backend supports nothing; `madlad` runs
   MADLAD-400 locally (`mt` extra).
5. **`rlr.resources`**: unfoldingWord figures of speech from the
   `bible-figures-of-speech` package, machine-translated into the LWC through
   the same backend, or read from the pre-rendered set in
   `src/rlr/data/renderings/`.

`rlr.agent.Pipeline.brief` composes the stages into a `Briefing`. Stages 4
and 5 are conditional.

## Non-negotiables

- **Trust is a feature.** Every result carries what it is, who produced it,
  when, and its license. Never present a text stripped of provenance.
- **Absence is a result.** When a stage cannot deliver, return `Unavailable`
  with a reason. An empty result is a bug; an explicit "nothing available for
  this LWC" is correct. Never return plausible fake data: a wrong verse in a
  language nobody on the team reads will not be caught downstream.
- **Stage 4 is optional at runtime.** Stages 1 to 3 and 5 must deliver value
  with back-translation entirely absent.
- **License data survives the pipeline.** It is filtered on and also
  displayed; do not discard it after filtering.

## Design constraints that shape code

Rationale and trade-offs in
[`docs/05-design-rationale.md`](docs/05-design-rationale.md); known
limitations in
[`docs/07-limitations-and-future-work.md`](docs/07-limitations-and-future-work.md).
The ones you are most likely to touch:

- **Retrieval takes a passage, not a verse.** `PassageRef` is a range. Do not
  bake a verse-only assumption into type signatures.
- **Display rights and derivative rights are separate.** No-derivatives texts
  are shown in stage 3; stages 4 and 5 refuse them with the license named.
- **Related languages by classification-path overlap**, with geographic
  distance reported alongside the score.
- **Machine translation is a backend protocol.** Add a backend by implementing
  `rlr.mt.Translator`; nothing else in the pipeline changes.

## Extension points

- New verse-indexed datasets implement `rlr.resources.VerseIndexedResource`
  (see `src/rlr/resources/__init__.py`).
- New MT backends implement `rlr.mt.Translator` and add a case to `rlr.mt.load_backend` so `RLR_MT` can select them.
- Pre-rendered translations: `rlr pretranslate --lwc <code> --book <BOOK>`
  writes to the cache; `--bundle` writes into the package data.

## Where things live

```
README.md                    orientation, for humans
AGENTS.md                    this file, for coding agents
docs/01..08                  the specification
src/rlr/{languages,catalog,verses,back_translation,resources}
src/rlr/{glottolog,ebible}.py  data access with a download cache (rlr.config)
src/rlr/mt.py                Translator protocol and backends
src/rlr/renderings.py        pre-rendered translations
src/rlr/agent.py             composes the stages, enforces provenance
src/rlr/cli.py               `rlr` entry point (brief, languages, serve, pretranslate)
src/rlr/demo/                FastAPI demo UI: server.py + static/ (no build step)
tests/                       offline; fixtures under tests/fixtures
```

## Working agreements

- `uv sync --extra dev --extra demo`, then `uv run pre-commit install`.
- `./run check` (or `just check`) runs the CI gate: ruff lint and format,
  mypy `strict`, pytest, on Python 3.12 and 3.13.
- Tests never touch the network. Add to `tests/fixtures` rather than reaching
  for live data.
- Live check: `uv run rlr brief --target ngq --lwc swh --passage "MRK 1:6"`.
