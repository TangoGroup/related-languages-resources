# RLR — Engineering Brief

> **Pass this file to Claude Code (or any LLM coding agent) at the start of a session.**
> It summarises the project, the pipeline, the decisions already made, the open
> questions, and where the detail lives.

---

## 1. What this is

**Related Languages Resources (RLR)** — a limited-scope prototype within the
Open QA Initiative. An agentic system that exposes Bible translation resources from
closely-related languages to translators doing QA on an in-process translation,
rendered where possible into a language the translator reads.

Approved to build. Stages 1, 2, 3 and 5 are implemented and run against live
data; stage 4 and LWC rendering are implemented behind a pluggable MT backend
that defaults to "none" and reports absence. Tests are offline, against
fixtures under `tests/fixtures`.

## 2. The pipeline

Given a translation context (target language, LWC, optional location) and a
passage of interest:

1. **`rlr.languages`** — identify closely-related languages. Glottolog
   classification-path overlap (Sean Boisen's in-house similarity measure) plus
   an areal score for shared countries, computed over the languages that have an
   eBible text. Reads Glottolog's CLDF export via `rlr.glottolog`; no 1 GB clone.
2. **`rlr.catalog`** — keep those with a usably-licensed Bible. eBible's
   `licences.tsv` is the license source (`rlr.ebible`). No-derivatives texts may be
   displayed but not rendered; `DISPLAYABLE` and `DERIVABLE` in `rlr.types` encode
   the two rights.
3. **`rlr.verses`** — retrieve the passage (`vref.txt`-indexed, verse-per-line,
   `<range>` markers and blank verses handled; multi-verse passages work).
4. **`rlr.back_translation`** — render into the LWC through an `rlr.mt.Translator`.
   Default backend supports nothing; `madlad` runs MADLAD-400 locally (`mt` extra).
   Scripture Forge (Serval API) remains a comparison, not a dependency.
5. **`rlr.resources`** — unfoldingWord figures of speech from the
   `bible-figures-of-speech` package (data bundled; `RLR_FIGURES_DIR` overrides),
   machine-translated into the LWC
   through the same backend.

Stages 4 and 5 are conditional. **When capability is absent, say so** — an empty
result is a bug, an explicit "nothing available for this LWC" is correct.

## 3. Non-negotiables

- **Trust is a feature.** Every result carries what it is, who produced it, when,
  and its license. Never present a text stripped of provenance.
- **Absence is a result.** See above.
- **Stage 4 is optional at runtime.** Stages 1–3 and 5 must deliver value with
  back-translation entirely absent (see D5).
- **License data survives the pipeline.** It is filtered *on* and also displayed;
  do not discard it after filtering.

## 4. Decisions already made

| | Decision |
|---|---|
| D1 | Proceed with the prototype |
| D2 | Build on Gloo's existing architecture; long-term home deferred |
| D3 | Target unit is verse *or pericope*; implement verse first, pericope if time |
| D4 | New-resource alerting is out of scope → future work |
| D5 | Keep Scripture Forge in scope until proven infeasible; don't depend on it |
| D6 | Fluent integration is a stretch goal |
| D7 | Stage 1 uses Glottolog path overlap, not a nearest-supported-language search |
| D8 | No-derivatives licenses are fine for display, not for rendering |
| D9 | Demo case is a Tanzanian target with Swahili as LWC; Biafada is a stretch case |
| D10 | Machine translation is in house (XRI); no third-party MT provider |

Full rationale: [`docs/05-decisions.md`](docs/05-decisions.md).

**D3 has a code consequence:** the retrieval interface takes a passage range,
not a single verse reference, even while only the single-verse case works.

## 5. Open questions — read before designing around them

| | Question | Status |
|---|---|---|
| Q1 | Is open-licensed-only acceptable? | **Resolved** (D8): yes, and no-derivatives texts may be displayed |
| Q2 | Is Scripture Forge administratively viable? | Unproven; Serval API is the technical path if credentials arrive |
| Q3 | Does the Lynx/Scripture Forge just-in-time integration exist? | Being checked with SIL |
| Q4 | How good is phylogenetic relatedness? | No ground truth; exclusion list implemented |
| Q5 | Does back-translation need an alignment-trained model? | Open; MADLAD drifts toward its Swahili Bible training data |
| Q6 | What speaks Kriol? | No MT yet; blocks Biafada's likeliest LWC |

Full detail: [`docs/06-open-questions.md`](docs/06-open-questions.md).

## 6. Success metrics

Six questions tracking the five stages; metrics 4 and 6 (back-translation
quality, MT quality) are explicitly qualitative judgments made by someone with
translation expertise. [`docs/07-success-metrics.md`](docs/07-success-metrics.md).

## 7. Where things live

```
README.md                    orientation, for humans
BRIEF.md                     this file, for agents
docs/01..08                  the specification
src/rlr/{languages,catalog,verses,back_translation,resources}
src/rlr/{glottolog,ebible}.py  data access with a download cache (rlr.config)
src/rlr/mt.py                Translator protocol and backends
src/rlr/agent.py             composes the stages, enforces provenance
src/rlr/cli.py               `rlr` entry point (brief, languages, serve)
src/rlr/demo/                FastAPI demo UI: server.py + static/ (no build step)
tests/                       offline; fixtures under tests/fixtures
```

## 8. Working agreements

- `uv sync --extra dev`, then `uv run pre-commit install`.
- ruff + mypy `strict` + pytest all gate CI across py3.12–3.13.
- Do not return plausible fake data from a stage that cannot deliver; return
  `Unavailable` with a reason. A wrong verse in a language nobody on the team
  reads is not a bug anyone will catch downstream.
- Tests never touch the network. Live checks: `uv run rlr brief --target ngq
  --lwc swh --passage "MRK 1:6"`.

## 9. Coordination

Project coordination, partner conversations and schedules live outside this
repository. The demo UI is `rlr serve` (see README); it needs the `demo` extra.
