# 8. Future work

Rough-draft content, described clearly enough to be prioritized and funded as
follow-on work if stakeholders concur that it is valuable.

Each entry uses the same structure:

1. Problem statement
2. User story
3. Brief technical description (approach, difficulty)

---

## New Resource Alerting

### Problem statement

Translation projects take years to complete, so more relevant resources may
become available in the course of a project. A team that checked for
related-language resources at project start has stale information by year two,
and no mechanism tells them otherwise.

### User story

> As a translation team on a multi-year project, I want to be told when a new
> resource becomes available in a language relevant to my project, so that I
> benefit from it without periodically re-searching sources I do not know about.

### Brief technical description

Builds directly on the RLR prototype. Given the capability to identify related
languages, monitor multiple sources — Open.Bible, DBL, Bible Aquifer, and others
— to:

- Detect when new, relevant resources become available.
- Build and describe access to those resources, possibly with translation or
  back-translation into the LWC.

**Difficulty:** moderate on the engineering, awkward on the evaluation. New
related resources appear slowly, which makes this hard to prototype in a natural
way — deferred from the main prototype for exactly that reason
([05-decisions.md](05-decisions.md) §D4). A funded version would need either a
long observation window or a synthetic backfill to demonstrate against.

---

## Verse-level audio from related-language audio Bibles

### Problem statement

In some cases an audio Bible exists in a related language where no usable text
does. For many minority languages, translators' oral skills are better than
their reading skills, so audio may be more useful to them than text — but audio
is typically distributed in chapter-sized units, which is unusable for
verse-level consultation.

### User story

> As a translator working on a verse, I want to hear the corresponding passage
> in a related language I understand when spoken, so that I can use an oral
> resource the same way I would use a written one.

### Brief technical description

Could an agentic system identify and extract the relevant verse audio from a
chapter-sized recording? Even an approximate extraction erring on the side of
more audio — for example, 30 seconds highly likely to contain the target content
somewhere — might be useful. A first approach could guess position from verse
lengths relative to the whole chapter.

**Difficulty:** potentially trivial. Some FCBH audio is distributed with
verse-level audio timing information, which would make extraction exact and
reduce this to a data-access problem. Establish whether the timing data covers
the languages of interest before building anything estimation-based.

---

## Back-translation generation and storage

### Problem statement

Back translations are often working documents. Aside from individual Paratext
projects, there is no known repository where they are stored — so even where a
back-translation exists, it is usually unreachable.

### User story

> As a translator, I want back-translations of related-language texts to exist
> and be retrievable, so that stage 4 of RLR has something to read.

### Brief technical description

Generation and storage may need to be part of RLR's value-add rather than
something it consumes. The alignment-based approach
([06-open-questions.md](06-open-questions.md) §Q5) — `eflomal` alignment between
related-language and LWC translations, identify the most literally-translated
verses, train a literal back-translation model — belongs here if it does not fit
the prototype's timeline.

**Difficulty:** high, and it is really a research project with a product
attached. Also independently useful: identifying the verses most often
translated most literally would help teams *starting* a translation, since
literal translations tend to be easiest and could get AI text or speech tools
working for them sooner.
