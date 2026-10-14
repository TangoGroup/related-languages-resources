"""``rlr`` command-line entry point.

The CLI is a development and evaluation surface, not the product. The product
is the agent surfacing results next to the verse a translator is working on.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from rlr.agent import build_pipeline
from rlr.config import Settings
from rlr.languages import suggest_lwcs
from rlr.mt import NoTranslator, load_backend, load_translator
from rlr.renderings import (
    RenderingFile,
    bundled_dir,
    file_name,
    note_texts,
    read_file,
    render_texts,
    write_file,
)
from rlr.resources.figures_of_speech import LICENSE_NAME, SOURCE_NAME, FiguresOfSpeech
from rlr.serialize import to_jsonable
from rlr.types import (
    PassageRef,
    PassageText,
    Provenance,
    TranslationContext,
    Unavailable,
    normalize_code,
)

app = typer.Typer(
    name="rlr",
    help="Related Languages Resources: Bible translation resources from nearby languages.",
    no_args_is_help=True,
)


def _context(
    target: str, lwc: str, exclude: list[str] | None, include: list[str] | None = None
) -> TranslationContext:
    return TranslationContext(
        target_language=target,
        lwc=lwc,
        excluded_languages=frozenset(exclude or ()),
        included_languages=frozenset(include or ()),
    )


def _provenance_line(p: Provenance) -> str:
    bits = [p.title]
    if p.publisher:
        bits.append(p.publisher)
    if p.published:
        bits.append(str(p.published))
    bits.append(p.license_name or f"license {p.license_class.value}")
    line = " · ".join(bits)
    return f"{line} [{p.source}]" + (f" <{p.url}>" if p.url else "")


@app.command()
def languages(
    target: str = typer.Option(..., help="Target language, ISO 639-3."),
    lwc: str = typer.Option("eng", help="Language of Wider Communication, ISO 639-3."),
    exclude: list[str] | None = typer.Option(None, help="Languages to leave out."),
    include: list[str] | None = typer.Option(
        None, help="Languages you know; consulted whether or not they are related."
    ),
    limit: int = typer.Option(10, help="Maximum languages to list."),
    min_similarity: float = typer.Option(0.5, help="Minimum Glottolog path similarity."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """List the languages with eBible texts that RLR considers related to the target."""
    settings = Settings.from_env()
    pipeline = build_pipeline(settings)
    pipeline.max_languages = limit
    pipeline.min_similarity = min_similarity
    related = pipeline.related_languages(_context(target, lwc, exclude))
    if isinstance(related, Unavailable):
        typer.echo(f"Nothing: {related.reason}")
        raise typer.Exit(code=1)
    if as_json:
        typer.echo(json.dumps(to_jsonable(related), indent=2, ensure_ascii=False))
        return
    if not related:
        typer.echo(f"No language with an eBible text scores >= {min_similarity} against {target}.")
        return
    for lang in related:
        editions = pipeline.corpus.editions_for(lang.code)
        licenses = ", ".join(sorted({e.provenance.license_name or "unknown" for e in editions}))
        flags = " (shared country)" if lang.shared_country else ""
        km = f", {lang.distance_km} km" if lang.distance_km is not None else ""
        typer.echo(
            f"{lang.similarity:.2f}  {lang.code:5s} {lang.name}{flags}{km}: "
            f"{len(editions)} edition(s), {licenses}",
        )
    if settings.lwc_csv is not None:
        suggestions = suggest_lwcs(target, settings.lwc_csv)
        if suggestions:
            typer.echo(
                "Likely LWCs: "
                + ", ".join(f"{s.name} ({s.code}, {s.probability:.2f})" for s in suggestions)
            )


def _echo_lwc_reading(reading: PassageText | Unavailable | None, lwc: str) -> None:
    if reading is None:
        return
    if isinstance(reading, Unavailable):
        typer.echo(f"== In {lwc}: not available. {reading.reason}")
    else:
        typer.echo(f"== In {lwc}")
        typer.echo(reading.text)
        typer.echo(f"   source: {_provenance_line(reading.provenance)}")
    typer.echo("")


@app.command()
def brief(
    target: str = typer.Option(..., help="Target language, ISO 639-3."),
    lwc: str = typer.Option(..., help="Language of Wider Communication, ISO 639-3."),
    passage: str = typer.Option(..., help="Passage reference, e.g. 'MRK 1:6' or 'MRK 1:4-8'."),
    exclude: list[str] | None = typer.Option(None, help="Languages to leave out."),
    include: list[str] | None = typer.Option(
        None, help="Languages you know; consulted whether or not they are related."
    ),
    limit: int = typer.Option(5, help="Maximum related languages to consult."),
    min_similarity: float = typer.Option(0.5, help="Minimum Glottolog path similarity."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Show related-language resources for a passage, with provenance."""
    try:
        ref = PassageRef.parse(passage)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from None
    settings = Settings.from_env()
    pipeline = build_pipeline(settings)
    pipeline.max_languages = limit
    pipeline.min_similarity = min_similarity
    briefing = pipeline.brief(_context(target, lwc, exclude, include), ref)
    if as_json:
        typer.echo(json.dumps(to_jsonable(briefing), indent=2, ensure_ascii=False))
        return

    typer.echo(f"{ref} for {target}, read in {lwc}")
    typer.echo("")
    _echo_lwc_reading(briefing.lwc_reading, lwc)
    if briefing.nothing_found:
        typer.echo(f"Related-language readings: none. {briefing.nothing_found.reason}")
    for reading in briefing.readings:
        lang = reading.language
        typer.echo(f"== {lang.name} ({lang.code}, similarity {lang.similarity:.2f})")
        typer.echo(reading.original.text)
        typer.echo(f"   source: {_provenance_line(reading.original.provenance)}")
        if reading.in_lwc is None:
            pass
        elif isinstance(reading.in_lwc, Unavailable):
            typer.echo(f"   in {lwc}: not available. {reading.in_lwc.reason}")
        else:
            typer.echo(f"   in {lwc}: {reading.in_lwc.text}")
            typer.echo(f"   rendering: {reading.in_lwc.provenance.source}")
        typer.echo("")
    if briefing.skipped and not briefing.nothing_found:
        typer.echo("Not shown: " + "; ".join(s.reason for s in briefing.skipped))
        typer.echo("")
    typer.echo("== Notes")
    if briefing.no_notes:
        typer.echo(f"None. {briefing.no_notes.reason}")
    for note in briefing.notes:
        typer.echo(f"-- {note.note.title} ({note.resource})")
        if isinstance(note.in_lwc, Unavailable):
            typer.echo(note.original.text)
            typer.echo(f"   in {lwc}: not available. {note.in_lwc.reason}")
        else:
            typer.echo(note.in_lwc.text)
            typer.echo(f"   rendering: {note.in_lwc.provenance.source}")
        typer.echo(f"   source: {_provenance_line(note.original.provenance)}")


@app.command()
def pretranslate(
    lwc: str = typer.Option(..., help="Target language to render the notes into, ISO 639-3."),
    book: list[str] | None = typer.Option(
        None, help="USFM book codes to cover (repeatable). Default: every book."
    ),
    batch_size: int = typer.Option(32, help="Sentences per generation batch."),
    bundle: bool = typer.Option(
        False, "--bundle", help="Write into the package's bundled data directory, for shipping."
    ),
    out: Path | None = typer.Option(None, help="Explicit output file (<lwc>.json.gz)."),
) -> None:
    """Render the figures-of-speech notes into an LWC once, so the demo needs no model."""
    lwc = normalize_code(lwc)
    settings = Settings.from_env()
    backend = load_backend(settings)
    if isinstance(backend, NoTranslator):
        typer.echo("pretranslate needs a live backend: set RLR_MT=madlad (uv sync --extra mt)")
        raise typer.Exit(code=2)
    resource = FiguresOfSpeech(settings.figures_dir)
    source = resource.source_language()
    if not backend.supports(source, lwc):
        typer.echo(f"{backend.name} cannot render {source} into {lwc}")
        raise typer.Exit(code=2)
    if out is None:
        root = Path(str(bundled_dir())) if bundle else settings.cache_dir / "renderings"
        out = root / file_name(lwc)
    books = [b.upper() for b in book] if book else resource.books()
    existing = (
        read_file(out)
        if out.exists()
        else RenderingFile(
            backend=backend.name,
            source=source,
            target=lwc,
            derived_from=SOURCE_NAME,
            license=LICENSE_NAME,
        )
    )
    texts = note_texts(n for b in books for n in resource.notes_in(b))
    typer.echo(f"{len(texts)} distinct strings across {len(books)} book(s); rendering into {lwc}")

    def progress(done: int, total: int) -> None:
        typer.echo(f"  {done}/{total}", nl=False)
        typer.echo("\r", nl=False)

    added = render_texts(
        texts, backend, source, lwc, existing, batch_size=batch_size, progress=progress
    )
    write_file(out, existing)
    typer.echo(f"{added} new rendering(s); {len(existing.entries)} total in {out}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind."),
    port: int = typer.Option(8765, help="Port to listen on."),
) -> None:
    """Serve the demo UI (needs the 'demo' extra: uv sync --extra demo)."""
    try:
        import uvicorn  # noqa: PLC0415

        from rlr.demo.server import create_app  # noqa: PLC0415
    except ImportError:
        typer.echo("The demo UI needs the 'demo' extra: uv sync --extra demo")
        raise typer.Exit(code=1) from None
    settings = Settings.from_env()
    if settings.mt_backend.strip() not in ("", "none"):
        typer.echo(
            f"Loading the {settings.mt_backend} machine-translation model "
            "(the first time this downloads about 11 GB)…"
        )
        warm = getattr(load_translator(settings), "warm_up", None)
        if callable(warm):
            warm()
    typer.echo(f"RLR demo at http://{host}:{port}  (first request downloads language data)")
    uvicorn.run(create_app(settings), host=host, port=port, log_level="warning")
