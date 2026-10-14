# 7. Known limitations and future work

## Known limitations

### Relatedness is unevaluated

There is no ground truth for "closely related", so the stage 1 ranking cannot
be scored against a reference. Whether a related language is *useful* depends
on what the translator can read. RLR exposes the score and the geographic
distance and lets the translator exclude or add languages
([05-design-rationale.md](05-design-rationale.md) §Related languages).

### Coverage, not technology, is often the limit

Only openly licensed texts are used. For some languages none of the closest
relatives has an open Bible. For Paraguayan Guarani (`gug`), for example, every
closely related language in the eBible Corpus carries a no-derivatives license:
those texts can be shown but not rendered into an LWC. Other languages have no
relatives in the corpus at all. RLR reports this rather than returning
nothing.

### Machine translation drifts toward memorised scripture

General multilingual models have seen Bibles in their training data. MADLAD-400
includes a Swahili Bible, and on scripture it tends to reproduce that text
rather than translate the source. Stage 4 output is a reading aid, not a
literal back-translation, and is labelled as machine output.

### Some LWCs have no machine translation

An LWC that no available model covers gets no rendering in stages 4 and 5.
Many smaller regional languages of wider communication fall in this gap, and
some are also absent from the eBible Corpus.

### Pericope boundaries need a dataset

Multi-verse passages work, but RLR cannot yet choose a pericope around a verse
on its own.

---

## Future work

Each entry gives a problem statement, a user story, and a technical sketch.

### Literal back-translation via alignment

**Problem.** A literal back-translation is what a translator wants from stage 4,
and general MT models do not produce one reliably.

**User story.**

> As a translator reading a related-language verse, I want a literal rendering
> in my LWC, so I can see how that translation handled the structure of the
> verse.

**Sketch.** Align a related-language translation with an LWC translation
(for example with `eflomal`), identify the most literally translated verses,
train a back-translation model on them, and use it on the rest. The same
alignment step identifies the verses most often translated literally, which is
independently useful to teams starting a translation. Alignment of this kind
has been used to infer semantic domains
([GUIDE](https://aclanthology.org/2024.sigtyp-1.2/)). This is a research
project with a product attached.

### Back-translation generation and storage

**Problem.** Back-translations are usually working documents inside individual
Paratext projects, so even where one exists it is rarely reachable.

**User story.**

> As a translator, I want back-translations of related-language texts to exist
> and be retrievable, so that stage 4 has something to read.

**Sketch.** Generate back-translations (with the approach above or a hosted
service such as Scripture Forge) and store them alongside the pre-rendered
translations RLR already ships.

### New-resource alerting

**Problem.** Translation projects run for years, and relevant resources appear
during them. A team that searched at project start has stale information by
year two.

**User story.**

> As a translation team on a multi-year project, I want to be told when a new
> resource becomes available in a language relevant to my project, so that I
> benefit from it without re-searching sources I do not know about.

**Sketch.** Given the related-language set from stage 1, monitor sources such
as Open.Bible, the Digital Bible Library and Bible Aquifer, detect new relevant
resources, and describe access to them, possibly rendered into the LWC. The
engineering is moderate; evaluation is awkward, because new resources appear
slowly. A demonstration needs either a long observation window or a synthetic
backfill.

### Verse-level audio from related-language audio Bibles

**Problem.** An audio Bible may exist in a related language where no usable
text does, and many translators' oral skills are stronger than their reading
skills. Audio is usually distributed by chapter, which is unusable for
verse-level consultation.

**User story.**

> As a translator working on a verse, I want to hear the corresponding passage
> in a related language I understand when spoken, so that I can use an oral
> resource the same way I would use a written one.

**Sketch.** Some Faith Comes By Hearing audio ships with verse-level timing,
which reduces extraction to data access. Where timing is absent, estimate the
position from verse lengths relative to the chapter and return a generous
window. Check timing coverage for the languages of interest first.

### More verse-indexed datasets

Any dataset keyed by verse reference (translator notes, key terms, Bible
Aquifer resources, Paratext Enhanced Resources) can be added as a
`VerseIndexedResource` and rendered into the LWC through the same translator.

### Integration with translation tools

The pipeline is a library with a CLI and an HTTP API, so it can be surfaced
inside translation environments as well as the standalone demo UI.
