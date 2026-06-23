"""
CLI Adapter for SkillHub Evaluation Engine.

Commands:
  run      — trigger a local evaluation (directly via engine, no HTTP)
  status   — check run status / report
  history  — list evaluation history
  confirm  — author confirms gap fields (writes to DB)
  serve    — start FastAPI server via uvicorn
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    help="SkillHub Evaluation Engine CLI",
    no_args_is_help=True,
)


def _make_repo(db_path_override: Optional[str]):
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings

    db_path = db_path_override or settings.eval_db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(db_path)
    repo.init_db()
    return repo


# ── run ───────────────────────────────────────────────────────────────────────

@app.command()
def run(
    bundle_path: str = typer.Argument(..., help="Path to Skill bundle directory"),
    skill_id: Optional[str] = typer.Option(None, "--skill-id", help="Override skill ID"),
    bundle_state: str = typer.Option("confirmed", "--bundle-state", help="Bundle state"),
    mode: str = typer.Option("capability_full", "--mode", help="Evaluation mode"),
    db_path: Optional[str] = typer.Option(None, "--db-path", envvar="EVAL_DB_PATH", help="Override DB path"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Trigger an evaluation run directly (no HTTP server needed)."""
    from skillhub_eval.core.engine import EvaluationEngine
    from skillhub_eval.core.schemas import BundleState, EvaluationMode
    from skillhub_eval.providers.factory import build_judge_providers
    from skillhub_eval.settings import settings

    try:
        bs = BundleState(bundle_state)
        em = EvaluationMode(mode)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if skill_id is None:
        skill_md = Path(bundle_path) / "SKILL.md"
        if skill_md.exists():
            for line in skill_md.read_text(encoding="utf-8").splitlines():
                if line.startswith("id:"):
                    skill_id = line.split(":", 1)[1].strip()
                    break
        if skill_id is None:
            skill_id = Path(bundle_path).name

    repo = _make_repo(db_path)
    ds, wb = build_judge_providers(settings)

    run_id = repo.create_run(
        skill_id=skill_id,
        skill_bundle_path=bundle_path,
        bundle_state=bundle_state,
        evaluation_mode=mode,
    )

    if not json_output:
        typer.echo(f"[run] run_id={run_id}  skill_id={skill_id}")
        typer.echo(f"[run] bundle_state={bundle_state}  mode={mode}")
        typer.echo("[run] Starting evaluation…")

    engine = EvaluationEngine(repo=repo, ds_provider=ds, wb_provider=wb)
    asyncio.run(
        engine.run_async(
            run_id=run_id,
            skill_bundle_path=bundle_path,
            bundle_state=bs,
            evaluation_mode=em,
        )
    )

    run_record = repo.get_run(run_id)
    result = {
        "run_id": run_id,
        "status": run_record["status"] if run_record else "unknown",
        "review_status": run_record.get("review_status") if run_record else None,
        "score_total": run_record.get("score_total") if run_record else None,
        "human_review_required": bool(run_record.get("human_review_required")) if run_record else False,
    }

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_run_result(result)


def _print_run_result(r: dict) -> None:
    review = r.get("review_status") or "—"
    score = r.get("score_total")
    score_str = f"{score}" if score is not None else "null (disagreement)"
    human = "⚠ human review required" if r.get("human_review_required") else ""
    color = typer.colors.GREEN if review == "pass" else (
        typer.colors.RED if review == "fail" else typer.colors.YELLOW
    )
    typer.echo("")
    typer.echo(f"  run_id       : {r['run_id']}")
    typer.echo(f"  status       : {r['status']}")
    typer.secho(f"  review_status: {review}", fg=color, bold=True)
    typer.echo(f"  score_total  : {score_str}")
    if human:
        typer.secho(f"  {human}", fg=typer.colors.YELLOW)


# ── status ────────────────────────────────────────────────────────────────────

@app.command()
def status(
    run_id: str = typer.Argument(..., help="Run ID to inspect"),
    db_path: Optional[str] = typer.Option(None, "--db-path", envvar="EVAL_DB_PATH"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show the current status and report for a given run_id."""
    repo = _make_repo(db_path)
    run_record = repo.get_run(run_id)
    if run_record is None:
        typer.echo(f"Error: run_id '{run_id}' not found.", err=True)
        raise typer.Exit(code=1)

    report = repo.get_report(run_id)
    result = {
        "run_id": run_id,
        "status": run_record["status"],
        "review_status": run_record.get("review_status"),
        "score_total": run_record.get("score_total"),
        "human_review_required": bool(run_record.get("human_review_required")),
        "report": report,
    }

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_run_result(result)
        if report and report.get("reason_codes"):
            typer.echo(f"  reason_codes : {', '.join(report['reason_codes'])}")


# ── history ───────────────────────────────────────────────────────────────────

@app.command()
def history(
    limit: int = typer.Option(20, "--limit", help="Max runs to show"),
    human_review_only: bool = typer.Option(False, "--human-review-only"),
    db_path: Optional[str] = typer.Option(None, "--db-path", envvar="EVAL_DB_PATH"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List evaluation history."""
    repo = _make_repo(db_path)
    runs = repo.list_history(
        limit=limit,
        human_review_required=True if human_review_only else None,
    )

    if json_output:
        typer.echo(json.dumps({"total": len(runs), "runs": runs}, indent=2, ensure_ascii=False))
        return

    if not runs:
        typer.echo("No runs found.")
        return

    header = f"{'RUN_ID':<38}  {'SKILL_ID':<30}  {'STATUS':<24}  {'REVIEW':<8}  {'SCORE':>6}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for r in runs:
        review = r.get("review_status") or "—"
        score = r.get("score_total")
        score_str = f"{score:5.1f}" if score is not None else " null"
        flag = " ⚠" if r.get("human_review_required") else "  "
        typer.echo(
            f"{r['run_id']:<38}  {r.get('skill_id','?'):<30}  "
            f"{r['status']:<24}  {review:<8}  {score_str}{flag}"
        )

    typer.echo(f"\n{len(runs)} run(s) shown.")


# ── confirm ───────────────────────────────────────────────────────────────────

@app.command()
def confirm(
    skill_id: str = typer.Argument(..., help="Skill ID to confirm gaps for"),
    field: Optional[list[str]] = typer.Option(None, "--field", help="field=value pair (repeatable)"),
    operator: str = typer.Option("cli_user", "--operator", help="Operator name"),
    db_path: Optional[str] = typer.Option(None, "--db-path", envvar="EVAL_DB_PATH"),
) -> None:
    """
    Author confirms gap fields for a Skill.

    Example: skillhub-eval confirm skill.abc --field "negative_prompts=do not PII" --operator alice
    """
    if not field:
        typer.echo("Error: provide at least one --field key=value", err=True)
        raise typer.Exit(code=1)

    confirmed_fields: dict[str, str] = {}
    for entry in field:
        if "=" not in entry:
            typer.echo(f"Error: invalid --field format '{entry}'. Expected key=value", err=True)
            raise typer.Exit(code=1)
        k, v = entry.split("=", 1)
        confirmed_fields[k.strip()] = v.strip()

    repo = _make_repo(db_path)
    for field_path, value in confirmed_fields.items():
        repo.save_confirmation(
            skill_id=skill_id,
            field_path=field_path,
            confirmed_value=value,
            operator=operator,
        )

    typer.secho(
        f"Confirmed {len(confirmed_fields)} field(s) for skill '{skill_id}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        f"Next: run `skillhub-eval run <bundle_path> "
        f"--skill-id {skill_id} --bundle-state confirmed --mode capability_full`"
    )


# ── serve ─────────────────────────────────────────────────────────────────────

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Start the FastAPI evaluation server."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("Error: uvicorn is not installed. Run: pip install uvicorn[standard]", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Starting SkillHub Eval server at http://{host}:{port}/ui/index.html")
    typer.echo(f"API docs: http://{host}:{port}/docs")
    uvicorn.run(
        "skillhub_eval.adapters.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
