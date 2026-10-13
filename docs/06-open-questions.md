# 6. Open questions

Q1 is resolved (see D8) and kept for the record. Q2–Q3 shape stage 4; Q4–Q5
affect quality; Q6 is new.

---

## Q1 — Is limiting the prototype to open-licensed Bibles acceptable?

Stated as a constraint question in the design doc: *is it acceptable for this
prototype to limit our capabilities to Bibles with open licenses (945 of them at
Open.Bible)?*

**Why it matters:** the doc's own worked example undercuts the assumption. For
Biafada, the five closest relatives are Wamey, Fulah, Gola, Mansoanka and Serer.
DBL has Bibles in Wamey, Gola and Serer — but none without a license agreement,
and Open.Bible has none of them. An open-license-only prototype returns *nothing*
for this example.

**Decided (2026-09-21):** yes; appropriate for what is really an MVP of a
tool.

**Consequence:** choose demonstration languages where open Bibles actually
exist among the related set, and be candid that coverage, not technology, is
the limiting factor.

**Residual sub-question:** does "open" include no-derivatives licenses for
*display*? In the eBible Corpus, 814 of the ~1080 texts with a known license
are `by-nc-nd` or `by-nd`. Those texts can be shown verbatim (stage 3) but not
back-translated or machine-translated (stages 4 and 5). For Biafada, Fulah is a
macrolanguage with five Fulfulde varieties in eBible, all `by-nc-nd`: with
no-derivatives allowed for display the example yields five readings, without it
none. Wamey, Gola, Mansoanka and Serer are not in eBible at all.

**Resolved (2026-09-23):** yes for display, no for derivatives. Recorded as
[D8](05-decisions.md).

---

## Q2 — Is Scripture Forge administratively viable for this prototype?

Requires Paratext credentials plus access granted by the SIL NLP team. Past
experience describes a very white-glove service; whether that has changed is
unknown.

Per [D5](05-decisions.md), explore until proven infeasible. The technical path
is known: Scripture Forge drafting is the Serval REST API
(`prod.serval-api.org`, public pretranslation endpoints). Who requests the
credentials is unassigned, alongside Q3. With MT in house (D10), stage 4 no
longer waits on this.

---

## Q3 — Is the Lynx / Scripture Forge "just-in-time" integration real?

There was at one point a just-in-time integration on the table, meant to
dynamically ingest translated material and produce drafts in near-real-time. If
it still exists it may be reachable by the agent via API, which would move stage
4 off the setup path and onto the request path.

**Action:** being checked with SIL; unassigned in this repository.

---

## Q4 — How good is phylogenetic relatedness, and how do we know?

Either tree-based measure runs without much effort, but there is no way to
evaluate how good the results are.

The working position: the results are what they are, and translators will have
to decide for themselves whether "related" means "useful" in their own context.
If they have no facility in a related language, it is not useful to them.

**Mitigation:** provide an exclusion list — *"I know Biafada but I don't know
Goma; don't show me results from this language in the future."* This weakens the
value proposition (it pushes judgment back to the user), but it is honest and it
is cheap.

**Mitigation implemented:** `TranslationContext.excluded_languages` and the
`--exclude` CLI option. Stage 1 uses the path-overlap measure (D7); its
geographic weakness is noted there.

---

## Q5 — Does back-translation need an alignment-trained model?

A richer proposal: use alignment (e.g. `eflomal`) between a related-language
translation and an LWC translation to identify the most literally-translated
verses, use those to train a back-translation model, and then back-translate the
non-aligned verses literally. Literal back-translation is what we actually want
here.

Precedent: this technique was used in
[GUIDE](https://aclanthology.org/2024.sigtyp-1.2/) to align well enough to infer
semantic domains.

**Tension to resolve.** Two different framings appeared in review:

- *The narrow one* — "I'm translating Mark 1:6 and want to see other examples of
  how John's garments were described." This needs retrieval, not model training.
- *The broad one* — train a literal back-translation model via alignment, which
  also identifies the verses most often translated most literally. That is
  independently useful for teams starting a translation, since literal
  translations tend to be easiest and could get AI text/speech tools working for
  them sooner.

The broad framing is a substantially larger build than the doc's main line.
Note also a stated modelling risk: getting models **not** to use memorized LWC
text.

**Unresolved sub-question:** back-translations are often working documents. Aside
from individual Paratext projects, there is no known place they are stored —
generation and storage may need to be part of RLR's value-add rather than
something it consumes.

---

## Q6 — What speaks Kriol?

Guinea-Bissau Kriol (`pov`) is the LWC a Biafada translator is likelier to
read than Portuguese: it has a full Bible in text and audio and is the usual
source text in that region. It is not in the eBible Corpus, and no in-house
text model covers it yet. Until something speaks Kriol, Biafada's LWC in RLR
is Portuguese, which has open eBible texts and MADLAD coverage. This is its
own roadmap item, not something stage 4 can absorb.

**Owner:** unassigned.
