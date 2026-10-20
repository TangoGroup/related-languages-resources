# 5. Design rationale

The constraints that shape RLR's code, and the trade-offs behind them. Each
section says what the system does, why, and where to change it.

---

## Trust is an output

Every text RLR shows a translator carries what it is, who produced it, when,
and under which license. `Provenance` is a constructor argument on every
result type, not an optional annotation, so a text cannot be built without it.

**Why:** translators decide whether a related-language reading is useful. They
can only do that if they know where it came from and whether they may use it
([02-jobs-to-be-done.md](02-jobs-to-be-done.md) §2.2).

---

## Absence is a result

A stage that cannot deliver returns `Unavailable` with a reason. An empty list
is a bug; "no machine translation into this LWC" is a correct answer.

**Why:** jobs 2.4 and 2.5 require it, and a silent gap is indistinguishable
from "nothing exists". RLR never substitutes plausible data for a missing
answer: a wrong verse in a language nobody on a review team reads will not be
caught downstream.

---

## Retrieval takes a passage, not a verse

The unit of interest is a verse *or* a pericope. In languages where participant
tracking and head-tail linkage shape what ends up in a verse, a single verse
can be too narrow to learn from.

**Consequence:** retrieval is addressed by `PassageRef`, a range. A single
verse is a range of one, so no call site has a verse-only code path.
Multi-verse retrieval works today; choosing pericope boundaries needs a
pericope dataset (see [07-limitations-and-future-work.md](07-limitations-and-future-work.md)).

---

## Related languages by classification-path overlap

Stage 1 scores each candidate by the overlap of its Glottolog classification
path with the target's, plus a flat areal score for cross-family neighbours
that share a country. The candidate set is the languages that have a text in
the eBible Corpus, so stages 1 and 2 answer one question together: which
usable texts are nearest to the target?

**Trade-off:** a tree-based measure is cheap, reproducible and needs no
training data, but on its own it is not geographic, and there is no ground
truth to evaluate it against. RLR ranks by the tree score damped by distance
(langfamilysim's `combined` score), ported as a few lines over the Glottolog
coordinates RLR already loads rather than taken as a dependency: the package
answers queries from a large precomputed `edges.csv`, and "clone and run"
should not need a local build of it. RLR reports both scores and the distance
and lets the translator correct the result: an exclusion list
(`TranslationContext.excluded_languages`, `--exclude`) removes languages they
cannot use, and an inclusion list (`included_languages`, `--include`, "Also
include" in the demo) adds languages they know whether or not the tree calls
them related.

**Extension point:** another similarity measure can replace
`rlr.glottolog.path_similarity` or `rlr.glottolog.combined_similarity` without
touching later stages.

---

## Display rights and derivative rights are separate

A no-derivatives license (CC BY-ND, CC BY-NC-ND) permits showing a text
verbatim but not translating it. Back-translation and machine translation are
derivative works.

**Consequence:** `LicenseClass` maps each source license to a class, and two
sets encode the two rights: `DISPLAYABLE` (open, non-commercial,
no-derivatives) governs stage 3, `DERIVABLE` (open, non-commercial) governs
stages 4 and 5. A no-derivatives text is shown in stage 3 and refused in
stages 4 and 5 with the license named. Because most eBible texts with a known
license forbid derivatives, this keeps far more readings available than an
open-only filter would. License data is filtered on and then displayed; it is
never discarded after filtering.

---

## Rendering into the LWC is optional

Stages 1 to 3 and 5 must deliver value with back-translation entirely absent.
The default machine-translation backend supports nothing and says so.

**Why:** machine-translation coverage varies widely by language, and many
deployments will have none for their LWC. When the LWC has an openly licensed
Bible of its own, RLR shows that text first and does not machine-translate the
related-language readings at all.

---

## Machine translation is a backend protocol

`rlr.mt.Translator` asks two questions: can you render this language pair, and
then do so. `NoTranslator` is the default; `MadladTranslator` runs MADLAD-400
locally through `transformers`. `CachedTranslator` serves pre-rendered
translations first and calls the live backend only for what they lack.

**Extension point:** a new backend implements `Translator` and adds a case to
`rlr.mt.load_backend` so `RLR_MT` can select it. Nothing else in the pipeline
changes. Hosted services (for example Scripture Forge, through the Serval API)
fit the same protocol; long-running draft generation belongs at setup time,
not on the request path.

---

## No language model on the request path

`Pipeline.brief` composes the stages deterministically. The jobs are retrieval
and rendering, and trust is easier to demonstrate when every string shown
traces to a file and a line. Machine translation is the only model in the
system, and its output is labelled as machine-generated with the backend named
in its provenance.

---

## Verse-indexed resources share one interface

Stage 5 ships one dataset, unfoldingWord's figures-of-speech notes, but treats
it as one implementation of `rlr.resources.VerseIndexedResource`. Any dataset
keyed by verse reference can be added the same way and is rendered into the
LWC through the same translator.

---

## Portability over coupling

The pipeline stages are independently testable and depend only on public data
sources and a translator protocol. Tests run offline against fixtures; nothing
in the package assumes a particular host, cloud or model provider.
