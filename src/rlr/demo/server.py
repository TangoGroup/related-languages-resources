"""FastAPI application for the demo UI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from rlr.config import Settings
from rlr.serialize import to_jsonable
from rlr.types import PassageRef, TranslationContext, Unavailable

if TYPE_CHECKING:
    from rlr.agent import Pipeline

STATIC_DIR = Path(__file__).parent / "static"


def _target_info(pipeline: Pipeline, code: str) -> dict[str, Any] | None:
    languoid = pipeline.glottolog.resolve(code)
    if languoid is None:
        return None
    return {
        "code": languoid.iso or code,
        "name": languoid.name,
        "glottocode": languoid.glottocode,
        "lat": languoid.lat,
        "lon": languoid.lon,
        "countries": list(languoid.countries),
        "family": languoid.family,
    }


def _codes(csv: str) -> frozenset[str]:
    return frozenset(c.strip() for c in csv.split(",") if c.strip())


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. The pipeline is constructed once, on first request."""
    resolved = settings or Settings.from_env()
    app = FastAPI(title="Related Languages Resources", version="0.0.0")

    @lru_cache(maxsize=1)
    def pipeline() -> Pipeline:
        from rlr.agent import build_pipeline  # noqa: PLC0415  (deferred: downloads data)

        return build_pipeline(resolved)

    app.state.get_pipeline = pipeline

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        p = app.state.get_pipeline()
        return {
            "languages_with_bibles": len(p.corpus.languages),
            "glottolog_languoids": len(p.glottolog),
            "verses": p.index.count_in(),
            "verses_total": len(p.index),
            "resources": [r.name for r in p.resources],
            "mt_backend": p.translator.name,
        }

    @app.get("/api/languages")
    def languages(
        target: str = Query(..., min_length=2),
        lwc: str = Query("eng"),
        limit: int = Query(10, ge=1, le=50),
        min_similarity: float = Query(0.5, ge=0.0, le=1.0),
        include: str = Query("", description="Comma-separated codes the reader knows."),
    ) -> JSONResponse:
        p = app.state.get_pipeline()
        p.max_languages = limit
        p.min_similarity = min_similarity
        ctx = TranslationContext(
            target_language=target.strip(), lwc=lwc.strip(), included_languages=_codes(include)
        )
        related = p.related_languages(ctx)
        if isinstance(related, Unavailable):
            raise HTTPException(status_code=404, detail=related.reason)
        rows = []
        for lang in related:
            editions = p.corpus.editions_for(lang.code)
            rows.append(
                {
                    **to_jsonable(lang),
                    "editions": [to_jsonable(e) for e in editions],
                },
            )
        suggestions: list[Any] = []
        if resolved.lwc_csv is not None and resolved.lwc_csv.exists():
            from rlr.languages import suggest_lwcs  # noqa: PLC0415

            suggestions = [
                to_jsonable(s) for s in suggest_lwcs(ctx.target_language, resolved.lwc_csv)
            ]
        return JSONResponse(
            {
                "target": _target_info(p, ctx.target_language),
                "lwc": _target_info(p, ctx.lwc),
                "related": rows,
                "lwc_suggestions": suggestions,
            },
        )

    @app.get("/api/brief")
    def brief(
        target: str = Query(..., min_length=2),
        lwc: str = Query(..., min_length=2),
        passage: str = Query(..., min_length=3),
        limit: int = Query(5, ge=1, le=50),
        min_similarity: float = Query(0.5, ge=0.0, le=1.0),
        exclude: str = Query("", description="Comma-separated codes to leave out."),
        include: str = Query("", description="Comma-separated codes the reader knows."),
    ) -> JSONResponse:
        try:
            ref = PassageRef.parse(passage)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        p = app.state.get_pipeline()
        p.max_languages = limit
        p.min_similarity = min_similarity
        ctx = TranslationContext(
            target_language=target.strip(),
            lwc=lwc.strip(),
            excluded_languages=_codes(exclude),
            included_languages=_codes(include),
        )
        briefing = p.brief(ctx, ref)
        payload = to_jsonable(briefing)
        payload["passage_label"] = str(ref)
        payload["target"] = _target_info(p, ctx.target_language)
        payload["lwc_info"] = _target_info(p, ctx.lwc)
        return JSONResponse(payload)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
