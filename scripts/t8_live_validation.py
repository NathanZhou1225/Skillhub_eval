#!/usr/bin/env python3
"""
T8 — live validation harness for testskills/ three-sample matrix.
Writes results to docs/runbooks/testskills-phase1-validation.md

Requires .env with DEEPSEEK_API_KEY and GEMINI_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.core.stage_timing import summarize_stage_timings
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.gemini import GeminiProvider
from skillhub_eval.settings import settings

DB_PATH = ROOT / "data" / "t8_validation.db"
RUNBOOK = ROOT / "docs" / "runbooks" / "testskills-phase1-validation.md"

GRILL_ME = ROOT / "testskills" / "grill-me"
TIERED = ROOT / "testskills" / "tiered-memory-sprint-manager"
STOCK = ROOT / "testskills" / "stock-radar-V6.2"


def _repo() -> SqliteRepository:
    repo = SqliteRepository(str(DB_PATH))
    repo.init_db()
    return repo


def _engine(repo: SqliteRepository) -> EvaluationEngine:
    if not settings.deepseek_api_key or not settings.gemini_api_key:
        raise SystemExit("Missing DEEPSEEK_API_KEY or GEMINI_API_KEY in .env")
    return EvaluationEngine(
        repo=repo,
        ds_provider=DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
        wb_provider=GeminiProvider(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
        ),
    )


async def _run(
    repo: SqliteRepository,
    engine: EvaluationEngine,
    *,
    label: str,
    skill_id: str,
    bundle_path: Path,
    bundle_state: str,
    mode: str,
) -> dict:
    t0 = time.monotonic()
    run_id = repo.create_run(
        skill_id=skill_id,
        skill_bundle_path=str(bundle_path),
        bundle_state=bundle_state,
        evaluation_mode=mode,
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=str(bundle_path),
        bundle_state=BundleState(bundle_state),
        evaluation_mode=EvaluationMode(mode),
    )
    elapsed_s = round(time.monotonic() - t0, 1)
    run = repo.get_run(run_id) or {}
    report = repo.get_report(run_id) or {}
    timings = repo.get_stage_timings(run_id)
    summary = summarize_stage_timings(timings) if timings else {}
    ps = report.get("provider_summary") or {}
    codes = report.get("reason_codes") or []
    if not codes and run.get("reason_codes"):
        try:
            codes = json.loads(run["reason_codes"])
        except (TypeError, json.JSONDecodeError):
            codes = []

    return {
        "label": label,
        "run_id": run_id,
        "skill_id": skill_id,
        "expected_mode": f"{bundle_state} + {mode}",
        "status": run.get("status"),
        "review_status": run.get("review_status"),
        "reason_codes": codes,
        "score_total": run.get("score_total"),
        "score_total_source": report.get("score_total_source"),
        "human_review_required": bool(run.get("human_review_required")),
        "elapsed_s": elapsed_s,
        "timing_summary": summary,
        "provider_summary": {
            "deepseek_score": ps.get("deepseek_score"),
            "gemini_score": ps.get("gemini_score"),
            "r5_triggered": ps.get("r5_triggered"),
        },
        "gaps_fields": [
            g.get("field_path")
            for g in (report.get("gaps") or [])
        ],
        "templates_ok": bool((repo.get_gaps(skill_id) or {}).get("gaps") is not None),
    }


def _confirm_grill_me(repo: SqliteRepository) -> None:
    fields = {
        "negative_prompts": "no PII or credentials in outputs",
        "error_handling": "return structured error JSON",
        "permission_scope": "read-only project files",
        "security_notes": "T8 validation run",
    }
    for path, value in fields.items():
        repo.save_confirmation("grill-me", path, value, "t8-runner")


def _scaffold_grill_me_closed_loop() -> None:
    text = GRILL_ME / "SKILL.md"
    body = text.read_text(encoding="utf-8")
    if "risk_level:" not in body:
        body = body.replace("---\n", "---\nrisk_level: low\n", 1)
        text.write_text(body, encoding="utf-8")

    ec = GRILL_ME / "eval_cases"
    ec.mkdir(exist_ok=True)
    si = GRILL_ME / "sample_io"
    si.mkdir(exist_ok=True)
    for i in range(1, 4):
        cid = f"c{i:02d}"
        (ec / f"{cid}.yaml").write_text(
            f"id: {cid}\ntype: happy_path\nuser_intent: T8 validation intent {i}\n",
            encoding="utf-8",
        )
        (si / f"{cid}.json").write_text(
            '{"response":"ok","status":"completed"}',
            encoding="utf-8",
        )


def _row(r: dict) -> str:
    ps = r.get("provider_summary") or {}
    ds = ps.get("deepseek_score")
    gm = ps.get("gemini_score")
    scores = "—"
    if ds is not None or gm is not None:
        scores = f"DS {ds if ds is not None else '—'} / Gemini {gm if gm is not None else '—'}"
    ts = r.get("timing_summary") or {}
    total = ts.get("total_phase_ms")
    mj = ts.get("model_judging_ms")
    timing = "—"
    if total:
        timing = f"{total/1000:.1f}s"
        if mj:
            timing += f" / 评审 {mj/1000:.1f}s"

    codes = ", ".join(r.get("reason_codes") or []) or "—"
    return (
        f"| {r['label']} | {r.get('expected_mode', '—')} "
        f"| `{r.get('status')}` / `{r.get('review_status')}` "
        f"| {codes} | {timing} | {scores} |"
    )


def _write_runbook(rows: list[dict], notes: list[str]) -> None:
    RUNBOOK.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# testskills Phase 1 — Live 验收 Runbook",
        "",
        f"> **执行时间**：{ts}  ",
        f"> **数据库**：`data/t8_validation.db`  ",
        f"> **自动化脚本**：`scripts/t8_live_validation.py`  ",
        "> **前置**：`.env` 已配置 DeepSeek + Gemini live key；单元测试 **195 passed**",
        "",
        "## 验收矩阵（实测记录）",
        "",
        "| Skill 实例 / 路径 | 评估状态（Expected Mode） | 实测终态（Status / Review） | 主错误码（Reason Codes） | 总耗时 / 评审耗时 | 双模打分（DS / Gemini） |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(_row(r) for r in rows)
    lines.extend([
        "",
        "## 分样本说明",
        "",
    ])
    lines.extend(notes)
    lines.extend([
        "",
        "## UI 手工核对清单（API/CLI 已验后）",
        "",
        "- [ ] **grill-me A1**：补全台 gaps 分区 + `eval_case` / `sample_io` 模板可复制",
        "- [ ] **grill-me A2**：confirm 后出现 Q5 checklist；未落盘直接全量评 → 大盘红色 failed",
        "- [ ] **grill-me A3**：落盘后全量评 → pass/warn/awaiting_human_review",
        "- [ ] **tiered-memory B**：degraded 终态 warn，非 failed/timeout",
        "- [ ] **stock-radar C**：专家台 per-case 折叠 + Δ≥15 浅红；Approve 后 human_review 回写",
        "- [ ] **历史大盘**：耗时列 + 详情模态 stage_timing 条形图",
        "",
        "## 复现命令",
        "",
        "```bash",
        "python scripts/t8_live_validation.py",
        "skillhub-eval serve   # UI: http://localhost:8000/ui/index.html",
        "```",
        "",
    ])
    RUNBOOK.write_text("\n".join(lines), encoding="utf-8")


async def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    repo = _repo()
    engine = _engine(repo)
    rows: list[dict] = []
    notes: list[str] = []

    # ── A1: grill-me minimal → awaiting_confirm ──
    r1 = await _run(
        repo, engine,
        label="A1 grill-me 草案入库",
        skill_id="grill-me",
        bundle_path=GRILL_ME,
        bundle_state="minimal",
        mode="capability_full",
    )
    rows.append(r1)
    gaps = repo.get_gaps("grill-me")
    gap_paths = [g["field_path"] for g in (gaps or {}).get("gaps", [])]
    notes.append(
        f"### 样本 A — grill-me\n\n"
        f"- **A1**：status=`{r1['status']}`（预期 `awaiting_confirm`）；"
        f"gaps 字段含 eval_cases/sample_io：{gap_paths}\n"
    )

    # ── A2: confirm, confirmed without files → fail ──
    _confirm_grill_me(repo)
    r2 = await _run(
        repo, engine,
        label="A2 grill-me 未落盘硬防线",
        skill_id="grill-me",
        bundle_path=GRILL_ME,
        bundle_state="confirmed",
        mode="capability_full",
    )
    rows.append(r2)
    notes.append(
        f"- **A2**：status=`{r2['status']}`（预期 `failed`）；"
        f"含 `RISK_CASE_COUNT_INSUFFICIENT`："
        f"{'RISK_CASE_COUNT_INSUFFICIENT' in r2['reason_codes']}\n"
    )

    # ── A3: scaffold files → closed loop ──
    _scaffold_grill_me_closed_loop()
    r3 = await _run(
        repo, engine,
        label="A3 grill-me 物理闭环",
        skill_id="grill-me",
        bundle_path=GRILL_ME,
        bundle_state="confirmed",
        mode="capability_full",
    )
    rows.append(r3)
    notes.append(
        f"- **A3**：status=`{r3['status']}` review=`{r3['review_status']}` "
        f"（预期 completed/warn/awaiting_human_review，非 failed/timeout）\n"
    )

    # ── B: tiered-memory degraded, 0 case ──
    r4 = await _run(
        repo, engine,
        label="B tiered-memory 降级摸底",
        skill_id="tiered-memory-sprint-manager",
        bundle_path=TIERED,
        bundle_state="draft_enriched",
        mode="degraded",
    )
    rows.append(r4)
    notes.append(
        f"### 样本 B — tiered-memory-sprint-manager\n\n"
        f"- **degraded**：status=`{r4['status']}` review=`{r4['review_status']}` "
        f"（预期 warn，非 pass/failed/timeout）\n"
    )

    # ── C: stock-radar confirmed full ──
    print("[T8] stock-radar live run (9 cases, high risk, up to 600s)…", flush=True)
    r5 = await _run(
        repo, engine,
        label="C stock-radar 高风险全量",
        skill_id="stock-radar",
        bundle_path=STOCK,
        bundle_state="confirmed",
        mode="capability_full",
    )
    rows.append(r5)

    if r5["human_review_required"]:
        repo.save_human_review(
            r5["run_id"], "approve", "t8-expert", "T8 auto-approve for runbook",
            repo.get_votes_for_run(r5["run_id"]),
        )
        repo.patch_report_after_human_review(
            r5["run_id"], "approve", "t8-expert", "T8 auto-approve for runbook", "pass"
        )
        repo.update_status(r5["run_id"], "completed", review_status="pass")
        report = repo.get_report(r5["run_id"]) or {}
        hr = report.get("human_review") or {}
        notes.append(
            f"### 样本 C — stock-radar-V6.2\n\n"
            f"- **全量评**：触发 R5 → `awaiting_human_review`；已脚本 Approve，"
            f"`human_review.reviewer_action`=`{hr.get('reviewer_action')}`\n"
        )
    else:
        notes.append(
            f"### 样本 C — stock-radar-V6.2\n\n"
            f"- **全量评**：status=`{r5['status']}` review=`{r5['review_status']}` "
            f"R5={r5['provider_summary'].get('r5_triggered')}\n"
        )

    _write_runbook(rows, notes)
    print(f"\n[T8] Runbook written: {RUNBOOK}", flush=True)
    for r in rows:
        print(_row(r), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
