"""Scenes for the recorded product demo: narration text plus what the camera does.

Each scene's ``action`` runs against a :class:`record.Stage` while its
narration plays; the recorder then waits out the rest of the clip plus ``pad``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: ElevenLabs premade voice "George" (warm, measured British narrator).
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
MODEL_ID = "eleven_multilingual_v2"


@dataclass(frozen=True)
class Scene:
    id: str
    text: str
    action: Callable[[Any], None]
    pad: float = 0.6


def intro(s: Any) -> None:
    s.scroll_top()
    s.point(".masthead__title", 0.3, 0.5, steps=40)
    s.settle(1.2)
    s.point(".masthead__dek", 0.4, 0.5, steps=40)


def the_query(s: Any) -> None:
    s.point("input[name=target]", 0.2, 0.5, steps=30)
    s.settle(1.6)
    s.point("input[name=lwc]", 0.2, 0.5, steps=24)
    s.settle(1.4)
    s.point("input[name=passage]", 0.3, 0.5, steps=24)
    s.settle(1.4)
    s.point("#target-name", 0.3, 0.5, steps=20)


def the_lwc(s: Any) -> None:
    s.scroll_to(".reading--lwc", offset=30)
    s.point(".reading--lwc .reading__text", 0.2, 0.4, steps=36)
    s.settle(3.0)
    s.point(".reading--lwc .reading__prov", 0.2, 0.5, steps=30)


def the_neighbourhood(s: Any) -> None:
    s.scroll_to(".constellation", offset=40)
    s.point("#map", 0.35, 0.45, steps=36)
    s.settle(2.2)
    s.point("#map", 0.6, 0.7, steps=36)
    s.settle(2.0)
    s.point("#ranking", 0.4, 0.3, steps=30)


def the_readings(s: Any) -> None:
    s.scroll_to(".reading:not(.reading--lwc)", offset=30)
    s.point(".reading:not(.reading--lwc) .reading__text", 0.15, 0.4, steps=36)
    s.settle(2.6)
    s.point(".reading:not(.reading--lwc) .similarity__bar", 0.5, 0.5, steps=30)
    s.settle(1.8)
    s.point(".reading:not(.reading--lwc) .reading__prov", 0.2, 0.5, steps=30)


def licenses(s: Any) -> None:
    s.scroll_to(".constellation", offset=40)
    s.point("#ranking .badge", 0.5, 0.5, steps=30)
    s.settle(2.4)
    s.scroll_to(".reading:not(.reading--lwc)", offset=30)
    s.point(".reading:not(.reading--lwc) .badge", 0.5, 0.5, steps=24)


def the_notes(s: Any) -> None:
    s.scroll_to(".notes", offset=30)
    s.point(".note", 0.4, 0.25, steps=36)
    s.settle(2.2)
    s.point(".note .rendering__text", 0.3, 0.5, steps=24)
    s.settle(2.6)
    s.point(".notes__grid .note:nth-child(2) .rendering__text", 0.4, 0.4, steps=30)
    s.settle(2.0)
    s.point(".note .note__prov", 0.3, 0.5, steps=24)


def also_include(s: Any) -> None:
    s.scroll_top()
    s.type_into("input[name=include]", "lug")
    s.settle(0.6)
    s.click(".stamp")
    s.wait_for_briefing()
    s.settle(0.8)
    s.scroll_to(".reading:not(.reading--lwc)", offset=30)
    s.point(".similarity--selected", 0.5, 0.5, steps=30)
    s.settle(1.4)
    s.scroll_to(".constellation", offset=40)
    s.point("#map .node--sel", 0.5, 0.5, steps=30)
    s.settle(2.2)
    s.page.fill("input[name=include]", "")


def konongo(s: Any) -> None:
    s.scroll_top()
    s.click("a[data-example='kcz|swh|MRK 1:2']")
    s.wait_for_briefing()
    s.point("#target-name", 0.3, 0.5, steps=24)
    s.settle(1.2)
    s.scroll_to(".constellation", offset=40)
    s.point("#ranking", 0.5, 0.5, steps=30)
    s.settle(2.0)
    s.scroll_to(".notes", offset=30)
    s.point(".note .rendering__text", 0.3, 0.5, steps=24)


def guarani(s: Any) -> None:
    s.scroll_top()
    s.click("a[data-example='gug|spa|LUK 2:7']")
    s.wait_for_briefing()
    s.point("#target-name", 0.3, 0.5, steps=24)
    s.settle(1.6)
    s.scroll_to(".reading:not(.reading--lwc)", offset=30)
    s.point(".reading:not(.reading--lwc) .badge", 0.5, 0.5, steps=30)
    s.settle(2.4)
    s.scroll_to(".notes", offset=30)


def closing(s: Any) -> None:
    s.scroll_top()
    s.click("a[data-example='ngq|swh|MRK 1:3']")
    s.wait_for_briefing()
    s.point(".masthead__title", 0.5, 0.5, steps=40)


SCENES: list[Scene] = [
    Scene(
        "intro",
        "This is Related Languages Resources, a prototype from the Open QA Initiative. "
        "A translator working on a verse rarely knows that the same verse already exists "
        "in a language next door to theirs; or where to find it; or whether they are "
        "allowed to use it. RLR finds it, shows it, and attaches the answers to all three "
        "questions, in a language the translator reads.",
        intro,
    ),
    Scene(
        "query",
        "Start with what the translator knows. The language they are translating into. "
        "The language they read comfortably. And the passage in front of them. Here the "
        "target is Ngoreme, a Bantu language of northern Tanzania; the language of wider "
        "communication is Swahili; and the passage is Mark, chapter one, verse three.",
        the_query,
    ),
    Scene(
        "lwc",
        "The first thing on the desk is the verse in the language the translator reads. "
        "Swahili has an open Bible, Biblia Takatifu, in the public domain, so RLR shows "
        "it before anything else. When the language of wider communication has an open "
        "Bible of its own, there is nothing to machine-translate; the translator can "
        "simply read it.",
        the_lwc,
    ),
    Scene(
        "neighbourhood",
        "Next, the neighbourhood. RLR walks Glottolog's classification of the world's "
        "languages to find the closest relatives that already have Scripture in the eBible "
        "Corpus. Each dot is a language with a Bible, placed by its coordinates; the nearer "
        "to Ngoreme on the family tree, the larger the dot. Suba, Kara, Isanzu, Pogolo, "
        "Ganda: all within a few hundred kilometres, ranked by how closely they are related.",
        the_neighbourhood,
    ),
    Scene(
        "readings",
        "For each of them, the verse itself, exactly as published, in the language's own "
        "orthography. The bar shows how closely related it is. And beneath every reading "
        "sits its provenance: the edition, who produced it, when, and the license it "
        "carries, with a link back to the source.",
        the_readings,
    ),
    Scene(
        "licenses",
        "The license is not decoration. Suba's New Testament is licensed no-derivatives, "
        "so RLR may show the text but never machine-translate it, and the badge says so. "
        "Kara's is Creative Commons Share-Alike, which permits a rendering. Every text "
        "carries its terms with it, and the system never does anything a license forbids.",
        licenses,
    ),
    Scene(
        "notes",
        "The passage also has translation notes: unfoldingWord's figures of speech, which "
        "exist only in English. Here they are in Swahili. A voice standing for a person. "
        "The metaphor of preparing a road. The Hebrew parallelism of the two lines. Each "
        "with its Greek kept as written, its comment, and the alternate renderings. These "
        "were translated once with an open model and ship with the software, so nothing "
        "runs on this machine, and the provenance says exactly where they came from.",
        the_notes,
    ),
    Scene(
        "include",
        "The tree is a guess about what might help. The translator knows better. Say they "
        "read Ganda: type it into Also include, and Ganda joins the desk at the top, marked "
        "as selected rather than scored, and takes its place on the map in ochre.",
        also_include,
        pad=2.0,
    ),
    Scene(
        "konongo",
        "Or change the language. Konongo, another Bantu language of Tanzania. Isanzu, "
        "Pogolo, Vwanji, Kinga, Kisi: five relatives with open licenses, and three figures "
        "of speech on the second verse of Mark, already in Swahili.",
        konongo,
    ),
    Scene(
        "guarani",
        "And when the data is thin, RLR is honest about it. For Paraguayan Guarani, "
        "Spanish has an open Bible, so that leads. The nearest Scripture is in Kaiwá, "
        "Mbyá and Bolivian Guaraní, under licenses that permit display only. The notes have "
        "nothing for this verse, and the page says so, rather than pretending.",
        guarani,
    ),
    Scene(
        "closing",
        "Everything you have seen is retrieval with a paper trail. Texts from the eBible "
        "Corpus, under their own licenses. Notes from unfoldingWord, rendered once with an "
        "open model and shipped as data. Classification from Glottolog. Nothing is "
        "invented, and nothing is shown without its source. Related Languages Resources: "
        "what already exists, next door.",
        closing,
        pad=1.0,
    ),
]
