"""Read-only JSON API backing the dashboard.

Every endpoint is a GET over fixture directories on disk plus an offline replay.
There is no write path, no database, and no authentication — by design, not by
omission. The app is safe to expose publicly because there is nothing to corrupt.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from replaygate.dashboard.models import DiffView, RunSummary
from replaygate.dashboard.service import (
    RunNotFound,
    UnknownCandidate,
    list_runs,
    load_run,
)


def create_app(fixtures_root: Path, frontend_dir: Path | None = None) -> FastAPI:
    """Build the app. ``frontend_dir`` is the built SPA; omit it to serve the API alone."""
    app = FastAPI(
        title="ReplayGate",
        description="Read-only view over recorded agent conversations.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "runs": len(list_runs(fixtures_root))}

    @app.get("/api/runs")
    def runs() -> dict[str, list[RunSummary]]:
        return {"runs": list_runs(fixtures_root)}

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str, candidate: str | None = Query(default=None)) -> DiffView:
        try:
            return load_run(fixtures_root, run_id, candidate)
        except RunNotFound:
            raise HTTPException(status_code=404, detail=f"no such run: {run_id}") from None
        except UnknownCandidate:
            raise HTTPException(
                status_code=404, detail=f"no such candidate: {candidate}"
            ) from None

    # Registered AFTER the real /api routes and BEFORE the SPA mount. Without it,
    # app.frontend's HTML fallback answers /api/typo with 200 index.html for any
    # client sending Accept: text/html.
    @app.api_route("/api/{rest:path}", methods=["GET", "HEAD"])
    def api_not_found(rest: str) -> None:
        raise HTTPException(status_code=404, detail=f"no such endpoint: /api/{rest}")

    if frontend_dir is not None:
        app.frontend("/", directory=frontend_dir, fallback="index.html", check_dir=False)

    return app
