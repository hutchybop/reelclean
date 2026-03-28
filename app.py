#!/usr/bin/env python3

"""Flask web interface for ReelClean workflows."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

from reelclean.core.config import ReelCleanConfig, discover_directory_options
from reelclean.core.models import Decision
from reelclean.core.tmdb import TMDBClient
from reelclean.web.job_manager import (
    MODE_QUALITY_ONLY,
    MODE_RENAME_AND_QUALITY,
    MODE_RENAME_ONLY,
    VALID_MODES,
    JobManager,
    JobNotFoundError,
)


load_dotenv()


def create_app() -> Flask:
    """Create and configure Flask application instance."""

    app = Flask(__name__)

    config = ReelCleanConfig.from_env()
    app.config["SECRET_KEY"] = config.flask_secret_key

    tmdb_client = TMDBClient(
        api_key=config.tmdb_api_key,
        timeout_seconds=config.tmdb_timeout_seconds,
    )
    manager = JobManager()

    mode_labels = {
        MODE_RENAME_ONLY: "Rename only",
        MODE_RENAME_AND_QUALITY: "Rename + quality check",
        MODE_QUALITY_ONLY: "Quality check only",
    }

    @app.context_processor
    def inject_globals() -> dict[str, object]:
        return {
            "mode_labels": mode_labels,
        }

    def resolve_allowed_dirs() -> list[tuple[str, str, Path]]:
        options = discover_directory_options(config)
        resolved: list[tuple[str, str, Path]] = []
        for option in options:
            try:
                path = option.path.expanduser().resolve()
            except OSError:
                continue
            resolved.append((option.label, str(path), path))
        return resolved

    def get_job_or_404(job_id: str):
        try:
            return manager.get_job(job_id)
        except JobNotFoundError:
            abort(404)

    @app.route("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index():
        allowed_dirs = resolve_allowed_dirs()
        jobs = manager.list_jobs()
        return render_template(
            "index.html",
            allowed_dirs=allowed_dirs,
            jobs=jobs,
            configured_tmdb=bool(config.tmdb_api_key),
        )

    @app.post("/jobs")
    def create_job_route():
        allowed_dirs = resolve_allowed_dirs()
        allowed_map = {value: path for _, value, path in allowed_dirs}

        mode = request.form.get("mode", MODE_RENAME_ONLY)
        selected_dir = request.form.get("directory", "")

        if mode not in VALID_MODES:
            flash("Invalid mode selection", "danger")
            return redirect(url_for("index"))

        if not allowed_map:
            flash("No directories configured. Set REELCLEAN_ALLOWED_DIRS.", "danger")
            return redirect(url_for("index"))

        root_dir = allowed_map.get(selected_dir)
        if root_dir is None:
            flash("Invalid directory selection", "danger")
            return redirect(url_for("index"))

        if not root_dir.exists() or not root_dir.is_dir():
            flash(f"Selected directory is not available: {root_dir}", "danger")
            return redirect(url_for("index"))

        job = manager.create_job(mode=mode, root_dir=root_dir, tmdb_client=tmdb_client)

        if mode == MODE_QUALITY_ONLY:
            manager.run_quality_stage(job.job_id, ffprobe_bin=config.ffprobe_bin)
            return redirect(url_for("quality_page", job_id=job.job_id))

        return redirect(url_for("dry_run_page", job_id=job.job_id))

    @app.get("/jobs/<job_id>")
    def job_overview(job_id: str):
        job = get_job_or_404(job_id)
        return render_template("job_overview.html", job=job)

    @app.get("/jobs/<job_id>/dry-run")
    def dry_run_page(job_id: str):
        job = get_job_or_404(job_id)
        if not job.includes_renaming:
            return redirect(url_for("quality_page", job_id=job_id))
        return render_template("dry_run.html", job=job)

    @app.post("/jobs/<job_id>/accept-all")
    def accept_all(job_id: str):
        manager.accept_all_ready(job_id)
        flash("Accepted all ready proposals", "success")
        return redirect(url_for("dry_run_page", job_id=job_id))

    @app.post("/jobs/<job_id>/movies/<movie_id>/decision")
    def set_movie_decision(job_id: str, movie_id: str):
        raw_decision = request.form.get("decision", "").strip().lower()
        if raw_decision == Decision.ACCEPT.value:
            manager.set_decision(job_id, movie_id, Decision.ACCEPT)
        elif raw_decision == Decision.SKIP.value:
            manager.set_decision(job_id, movie_id, Decision.SKIP)
        else:
            flash("Invalid decision action", "danger")

        return redirect(url_for("dry_run_page", job_id=job_id))

    @app.post("/jobs/<job_id>/movies/<movie_id>/retry")
    def retry_movie(job_id: str, movie_id: str):
        search_term = request.form.get("search_term", "").strip()
        if not search_term:
            flash("Retry search term cannot be empty", "danger")
            return redirect(url_for("dry_run_page", job_id=job_id))

        manager.retry_movie(
            job_id=job_id,
            movie_id=movie_id,
            search_term=search_term,
            tmdb_client=tmdb_client,
        )
        flash("Re-ran TMDB lookup for selected movie", "success")
        return redirect(url_for("dry_run_page", job_id=job_id))

    @app.post("/jobs/<job_id>/run-renames")
    def run_renames(job_id: str):
        manager.run_rename_stage(job_id)
        flash("Rename stage complete. Review cleanup candidates next.", "success")
        return redirect(url_for("cleanup_page", job_id=job_id))

    @app.get("/jobs/<job_id>/cleanup")
    def cleanup_page(job_id: str):
        job = get_job_or_404(job_id)
        if not job.includes_renaming:
            return redirect(url_for("results_page", job_id=job_id))
        if job.status not in {"awaiting_cleanup", "completed"}:
            flash("Run the rename stage before cleanup.", "warning")
            return redirect(url_for("dry_run_page", job_id=job_id))
        return render_template("cleanup.html", job=job)

    @app.post("/jobs/<job_id>/cleanup")
    def run_cleanup(job_id: str):
        job_before = get_job_or_404(job_id)
        if job_before.status not in {"awaiting_cleanup", "completed"}:
            flash("Run the rename stage before cleanup.", "warning")
            return redirect(url_for("dry_run_page", job_id=job_id))

        selected_ids = request.form.getlist("candidate_ids")
        job = manager.run_cleanup_stage(
            job_id=job_id,
            selected_candidate_ids=selected_ids,
            ffprobe_bin=config.ffprobe_bin,
        )

        flash("Cleanup stage complete", "success")
        if job.includes_quality:
            return redirect(url_for("quality_page", job_id=job.job_id))
        return redirect(url_for("results_page", job_id=job.job_id))

    @app.get("/jobs/<job_id>/results")
    def results_page(job_id: str):
        job = get_job_or_404(job_id)
        if job.includes_quality and job.quality_results:
            return redirect(url_for("quality_page", job_id=job_id))
        return render_template("results.html", job=job)

    @app.get("/jobs/<job_id>/quality")
    def quality_page(job_id: str):
        job = get_job_or_404(job_id)
        if not job.includes_quality:
            return redirect(url_for("results_page", job_id=job_id))
        return render_template("quality.html", job=job)

    return app


app = create_app()


if __name__ == "__main__":
    cfg = ReelCleanConfig.from_env()
    app.run(host=cfg.reelclean_host, port=cfg.reelclean_port, debug=False)
