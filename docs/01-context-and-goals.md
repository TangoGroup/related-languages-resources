# 1. Context and goals

## Context

The OpenQA project includes producing an MVP open-source agentic tool suite that
Bible translation organizations can adopt and extend. RLR is one component of
that suite: an agentic system that exposes resources from related languages to
translators doing quality assurance on translations in-process.

## Problem statement

A wide variety of Bible translation resources — including translations
themselves — exist in many languages. In some cases a completed translation and
other relevant content (Paratext Enhanced Resources, Bible Aquifer resources,
translator notes, and so on) already exists in a closely-related language:
either one in the same language family, or one used in the same geographic
region as a Language of Wider Communication (LWC).

Translators with limited technology experience may not be able to reach any of
it. The content is:

- **hard to discover** — it comes from external information systems translators
  are unaware of;
- **hard to access** — it requires skills in web search and website navigation;
- **hard to read** — it may not be available in languages familiar to the
  translator.

## Purpose

RLR prototypes the capability to give translators easy access to content from
existing translations and Bible translation resources, preferably in a familiar
language. It combines several functions:

1. Given a translation context (target language and LWC, perhaps together with
   geographic location), identify closely-related languages.
2. For those languages, retrieve the subset that also have an existing and
   available Bible translation.
3. For those Bibles, given a particular verse of interest, return the
   corresponding texts for that verse, as examples of how the verse might be
   translated.
4. Back-translate those corresponding texts into the LWC for easier
   understanding, where back-translation capability exists for the LWC.
5. Translate selected other resources that are indexed by verse but available
   only in English into the LWC, where English→LWC machine translation exists.
   For this prototype, figures-of-speech data from unfoldingWord is the example
   dataset.

## Scope

This is a **limited-scope prototype**. In scope:

- The five functions above.
- Demonstrating integration with **Fluent** — recorded in the source doc as
  "nice to have, depending on feasibility", so treat it as a stretch goal rather
  than a commitment.

Explicitly deferred (see [08-future-work.md](08-future-work.md)):

- Alerting translators when new relevant resources appear.
- Extracting verse-level audio from related-language audio Bibles.

## Audience

The primary audience is quality assurance personnel:

- A **translator**, checking her own or another's output, who holds the primary
  knowledge of the target language.
- A **translation consultant or advisor**, who may have more limited facility in
  the target language but more technical expertise.
- **Community organizations and ministries** reviewing a translation prior to
  publication.

These differ in what they can read, not only in expertise — which is precisely
why the LWC rendering path matters as much as the retrieval path.
