# 5. Decisions

Decisions taken during review of the design doc, with the reasoning that
produced them. Each is revisitable; none is currently under revision.

---

## D1 — Proceed with the prototype

**Decided.** The prototype proposal was approved for build.

---

## D2 — Build on Gloo's existing architecture

**Question raised:** are we proposing to build on Gloo's proprietary LLM
architecture?

**Decided:** yes, for now. Build on the architecture we already have,
understand, and control.

**Rationale:** where RLR lives long-term is explicitly a question to defer — "a
can to kick down the road". Deciding it now would buy nothing and cost time.

**Implication:** do not design for portability at the cost of speed, but do not
gratuitously couple to Gloo internals either. The pipeline stages are
independently testable for exactly this reason.

---

## D3 — Verse first, pericope after

**Question raised:** verse level may be too narrow. In languages where
participant tracking and head-tail linkage affect what ends up in a verse, a
wider chunk may be necessary for a team to benefit from what they see in a
particular verse.

**Decided:** broaden the target unit to *either verse or pericope*. For
implementation, start with verse (easier) and expand to pericope if there is
time — which appears doable. A pericope dataset can be supplied.

**Implication:** the retrieval interface should take a passage range, not a
single verse reference, even while only the single-verse case is implemented.
Do not bake a verse-only assumption into the type signatures.

---

## D4 — New-resource alerting is out of scope

**Idea raised:** teams would eventually like notice when new resources become
available in a relevant language. Translation runs on a timescale of years, so
the set of relevant resources will grow during a project.

**Decided:** valuable, but out of scope here. It is hard to prototype naturally
— new related resources appear slowly — so it moves to future work.

**Where it went:** [08-future-work.md](08-future-work.md) §New Resource Alerting.

---

## D5 — Keep Scripture Forge in scope until proven infeasible

**Concern raised:** Scripture Forge access was a real bottleneck in past
experience; the service was still very white glove.

**Decided:** back-translation may end up being "nice to have" and can move to
future ideas if it proves untenable — but explore it unless and until it is
proven infeasible.

**Implication:** do not design the rest of the system to depend on stage 4.
Stages 1–3 and 5 must deliver value with stage 4 absent.

---

## D6 — Fluent integration is a stretch goal

**Decided:** integration with Fluent is "nice to have, depending on
feasibility". Demonstrate it if the core pipeline lands with time to spare.

---

## D7 — Stage 1 scores by Glottolog path overlap

**Decided (2026-09-23):** base stage 1 on the classification-path overlap
measure rather than the nearest-supported-language search, and swap later if
that makes sense, or pivot to something more geographically aware. The
nearest-supported search answers a speech-tooling question (which supported
language is closest); RLR's candidate set is languages with an eBible text.

**Implication:** `rlr.glottolog` reads the CLDF export; `rlr.languages` scores
eBible languages against the target and reports distance alongside the score.

---

## D8 — No-derivatives licenses are fine for display

**Decided (2026-09-23):** by-nc-nd is acceptable for simple retrieval of
Bible text, but not for back-translation into an LWC. For the prototype, a
couple of related languages with usable Bibles is good enough. Closes the
residual part of Q1.

**Implication:** `DISPLAYABLE` includes `DERIVATIVES_FORBIDDEN`; `DERIVABLE`
does not. Stage 3 shows the text; stages 4 and 5 refuse with the license named.

---

## D9 — Demo case: a Tanzanian target with Swahili as LWC

**Decided (2026-09-23):** the demo is a Tanzanian target (Ngoreme `ngq` or
Konongo-Ruwila `kcz`) with Swahili as LWC. Nine Tanzanian eBible texts are
derivative-friendly, Swahili has public-domain and CC-BY-SA editions, and
in-house MT covers Swahili. Biafada (Guinea-Bissau) is a stretch case: its
relatives in eBible are all no-derivatives, and no MT speaks Kriol.

---

## D10 — Machine translation is in house

**Decided (2026-09-23):** RLR's MT comes from in-house models, not a
third-party provider. `rlr.mt` is a small backend protocol; MADLAD-400 is the
first concrete backend.
