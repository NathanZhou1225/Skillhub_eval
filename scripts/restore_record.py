"""Incident recovery: rebuild RECORD.md from git 88f5891 + W8 patches.

Not for daily RECORD updates — patch sections in place or update Sprint first.
Default is dry-run; pass --write to overwrite RECORD.md or --output to save elsewhere.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "88f5891"


def restore_record_text(root: Path = ROOT) -> str:
    text = subprocess.check_output(
        ["git", "show", f"{BASE_COMMIT}:RECORD.md"], cwd=root
    ).decode("utf-8-sig")
    text = text.replace(".cursor_memory", ".project_memory")

    old_boundary = (
        "**W5.5 安全 gate 分层 + 拦截 UX** ✅（`bundle_security`；**511 tests**）。"
        "**OpenSpec 活跃 change 已清空**。**不重写** 1.2 准入阈值（85/70/90）。"
        "**当前主线：W5.5 收尾**（剧本 B/C + runbook）→ **W7 服务器彩排**；"
        "集市生态（原 W6）已移至阶段四。阶段二可选收尾已取消。"
    )
    new_boundary = (
        "**W5.5 安全 gate 分层 + 拦截 UX** ✅（`bundle_security`；**511 tests**）。"
        "**W5.5 回归 fixture 三件套 + 评估结果/拦截 UX 热修** ✅（"
        "`testskills/stock-radar-fixture-{sec-block,score-low,score-high}`；"
        "fail 红标、`security_blocked` 可读说明、共识 fail 聚合、`skill_summary` 兜底；**524 tests**）。"
        "**W8 本地 Agent 执行桥** ✅ **代码落地**（OpenSpec `local-agent-exec-bridge` 23/23 tasks；"
        "**583 tests**；DB v9 `spot_check_eligible`/`execution_source_used`；"
        "fixture `testskills/exec-fixture-minimal` + runbook）— "
        "**待用户网页/CLI 实机验收后归档**。OpenSpec 活跃 change：`local-agent-exec-bridge`。"
        "**不重写** 1.2 准入阈值（85/70/90）。**当前主线**：W8 实机验收 → `/opsx:archive` → "
        "**W7 服务器彩排**；W8.4 多 agent 对照统计待排；W5.5 剧本 B/C + runbook 作为并行小尾。"
        "集市生态（原 W6）/ W10 已移至阶段四。阶段二可选收尾已取消。"
    )
    if old_boundary not in text:
        raise SystemExit("boundary block not found in base commit; aborting")
    text = text.replace(old_boundary, new_boundary)

    old_waves = (
        "| **W7** | 评估系统服务器彩排（release zip + smoke + deployment runbook） | "
        "🟡 待启动（W5.5 后） |\n"
        "| ~~**W6**~~ | ~~集市生态~~ | **已移至阶段四**（见 `SPRINT_phase4-marketplace-biz.md`） |"
    )
    new_waves = (
        "| **W8（重定义）** | **本地 Agent 执行桥**（穿透本地 CLI agent 真跑 skill → "
        "回传真实产出 → 复用 judge）；**取代原 W8 Level 2 沙盒 + 原 W9 自建 Harness** | "
        "✅ **代码落地**（583 tests）；🟡 **待实机验收** |\n"
        "| **W7（重定位）** | 服务器彩排：服务端仅承载 **judge + 公网中央复核**；executor 留本地 | "
        "🟡 W8 纵切通过后 |\n"
        "| ~~**W8 Level 2 沙盒**~~ | ~~引擎接 `PythonSubprocessRunner`~~ | "
        "**已废弃**（2026-06-17）：本地 agent 跑任务时已执行脚本，中央代码跑冗余 |\n"
        "| ~~**W9 自建 Harness**~~ | ~~中央 Agent Harness~~ | "
        "**已废弃**（2026-06-17）：本地 agent 即分布式 Harness |\n"
        "| ~~**W6**~~ | ~~集市生态~~ | **已移至阶段四**（见 `SPRINT_phase4-marketplace-biz.md`） |"
    )
    if old_waves not in text:
        raise SystemExit("wave table block not found in base commit; aborting")
    text = text.replace(old_waves, new_waves)

    in_progress_marker = (
        "| **W4.5 provider-env-factory** | **🟡 待启动** — 双评审槽位完全 env 驱动 |"
    )
    w8_progress = (
        "| **W5.5 回归 fixture + 拦截 UX 热修** | **✅ 收官** — 三 fixture + UI fail 红标/说明；"
        "**524 tests** |\n"
        "| **W8 本地 Agent 执行桥** | **✅ 代码落地** — OpenSpec `local-agent-exec-bridge` 23/23；"
        "**583 tests**；🟡 **待网页/CLI 实机验收** |\n"
        + in_progress_marker
    )
    if in_progress_marker not in text:
        raise SystemExit("in-progress marker not found in base commit; aborting")
    text = text.replace(in_progress_marker, w8_progress)

    old_opening = (
        "> 阶段三定位：**评估系统完善**（不做集市）。**W0–W5.4 已收官**（498 tests）；"
        "**W5.5 安全 gate 分层热修** ✅（**511 tests**）。"
        "本窗口主线：**W5.5 Demo 验收**（剧本 B/C + runbook）。必读 `RECORD.md`、"
        "`.project_memory/active/SPRINT_phase3-eval-system.md`。**不重写** 1.2 阈值。"
        "集市 listing / Trending / NL 搜索见 **阶段四** `SPRINT_phase4-marketplace-biz.md`。"
    )
    new_opening = (
        "> 阶段三定位：**评估系统完善**（不做集市）。**W0–W5.5 已收官**（524 tests）；"
        "**W8 本地 Agent 执行桥** ✅ **代码落地**（583 tests）。"
        "本窗口主线：**W8 实机验收**（`docs/runbooks/local-agent-exec-validation.md` + "
        "`RUN_LOCAL_AGENT=1`）→ `/opsx:archive` → W7。必读 `RECORD.md`、"
        "`.project_memory/active/SPRINT_phase3-eval-system.md`、回归包 `testskills/README-fixtures.md`。"
        "**不重写** 1.2 阈值。集市 listing / Trending / NL 搜索见 **阶段四** "
        "`SPRINT_phase4-marketplace-biz.md`。"
    )
    if old_opening not in text:
        raise SystemExit("opening block not found in base commit; aborting")
    text = text.replace(old_opening, new_opening)

    q_insert = (
        "| **Q-19** | **Level 2 隔离试跑未接入主引擎**：标准规定中/高风险 Pass 须试跑级，"
        "当前实际读 sample_io 样例文件 | P1 | **W8 已落地（2026-06-17）**：`ExecutionSource` + "
        "本地 agent；🟡 待实机验收 |\n"
        "| **Q-20** | **中央 subprocess 沙盒跑不了内网 skill**（无 VPN/DB） | P1 | "
        "**W8 路线已定**：穿透本地 CLI agent；中央 judge 复用 |\n"
        "| **Q-21** | **被穿透的本地 agent 以 `bypassPermissions`/`--trust` 全自动跑任意 skill 代码**"
        "（含内网权限机器），本身是攻击面 | P1 | **W8.5 已落地**：执行前 consent gate + "
        "Security Gate + output sanitizer + `HardenedProfile`（codex 红线） |\n"
        "| **Q-22** | **回传契约怎么定**：actual_output 应含 agent 最终文本 **+** `tool_result`"
        "（skill 被调用时真实产出 + exit_code）/ usage/duration | P1 | **W8 已落地**："
        "stream-json 流解析统一契约（grill G1）；见 design D3 |\n\n"
    )
    marker = "## 已做决策\n"
    if "**Q-19**" not in text.split("## 已做决策")[0][-800:]:
        text = text.replace(marker, q_insert + marker)

    w8_decisions = (
        "| **执行层路线重定向（2026-06-17）** | 调研 `nexu-io/open-design`（local-first，"
        "穿透本地 CLI agent）；确定 **W8 重定义 = 本地 Agent 执行桥**；废弃中央 Level 2 沙盒 + "
        "W9 自建 Harness；W10 移阶段四 | 继续中央 subprocess 沙盒（内网 skill 结构性不可行）；"
        "自建中央 Harness（与开发者已有 CLI agent 重复） |\n"
        "| **W8 回传契约：流解析非 MCP**（grill G1） | cursor/codex 无 MCP 注入；"
        "统一解析 stream-json 取最终文本 + tool_result + cwd 产物 | MCP `submit_case_output`"
        "（仅 claude 可用，不通用） |\n"
        "| **W8 judge 双 prompt**（grill G2） | 真跑 → 执行结果 rubric；sample_io 回退 → "
        "现有 doc-centric prompt | prompt 不动直接填 actual_output（红线口径自相矛盾） |\n"
        "| **W8 level_2 = 本地真跑 + entrypoint 证据** | 废弃 `has_scripts AND self.sandbox`；"
        "PASS 本地真跑标 `spot_check_eligible` | 仅信文本输出（agent 可绕 pipeline 手写） |\n"
        "| **W8 v1 三 agent 顺序 claude→codex→cursor-agent** | DX 最低门槛；"
        "顺序按流解析器复杂度/红线能力 | v1 只打通 1 个；全量 agent（YAGNI） |\n"
        "| **W8 红线隔离** | 红线真跑仅在 codex 加固档；claude/cursor 无加固 → "
        "红线降级 doc-centric | 原生 Windows 防火墙 ACL（脆弱）；强行全 WSL |\n"
        "| **W8 信任 v1** | judge pass → PASS + `spot_check_eligible`；"
        "专家抽检纯人工但 history 可筛 | v1 建中央复跑（过早）；永久信任（多用户泄漏） |\n"
        "| **砍掉中央代码执行，不留冗余 `PythonSubprocessRunner`** | 本地 agent 跑任务时已执行 "
        "skill 脚本，中央再跑 python 冗余；组件留架子供阶段四 Golden Case 按需接 | "
        "物理删除 runner（阶段四可能需确定性复跑） |\n"
        "| **执行前 consent 进程内 gate（无 UI）**（W8.5） | v1 用 `EXEC_CONSENT_REQUIRED` + "
        "`grant_exec_consent(skill_id)`；Demo 走 CLI/文档 | 首版就做 UI 同意弹窗（阻塞 W8 纵切） |\n"
    )
    sec_decision = "| **W5.5 安全 gate 分层扫描** |"
    if "**执行层路线重定向（2026-06-17）**" not in text:
        text = text.replace(sec_decision, w8_decisions + sec_decision)

    refs_insert = (
        "| **W8 本地 Agent 执行桥 runbook** | `docs/runbooks/local-agent-exec-validation.md` |\n"
        "| **W8 OpenSpec change（待归档）** | `openspec/changes/local-agent-exec-bridge/` |\n"
        "| **W8 设计稿** | `docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md` |\n"
        "| **W8 exec fixture** | `testskills/exec-fixture-minimal/` |\n"
        "| **Skill 评估系统全景说明 §10** | `docs/guides/Skill评估系统全景说明.md` |\n"
    )
    ref_marker = "| W5.5 会话归档 change |"
    if "W8 本地 Agent 执行桥 runbook" not in text:
        text = text.replace(ref_marker, refs_insert + ref_marker)

    changelog = (
        "| 2026-06-16 | **验证工程现状文档化**：`docs/guides/Skill评估系统全景说明.md` **v2.1** "
        "新增 **§10**（设计 vs 现状、sample_io 来源、能力边界、演进路线） |\n"
        "| 2026-06-17 | **执行层路线重定向（脑暴前定标）**：调研 `nexu-io/open-design`（local-first，"
        "穿透本地 CLI agent）；确定 **W8 重定义 = 本地 Agent 执行桥**；废弃 W8 Level 2 沙盒 + "
        "W9 Harness；W10 移阶段四 |\n"
        "| 2026-06-17 | **W8 设计稿 + OpenSpec change + grill 收口**：设计稿 "
        "`docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md`；"
        "OpenSpec `local-agent-exec-bridge`；grill 11 项修订 |\n"
        "| 2026-06-17 | **W8 本地 Agent 执行桥代码落地**：OpenSpec tasks 1–23 完成；"
        "**583 tests**；DB v9；fixture + runbook；🟡 待实机验收 |\n"
        "| 2026-06-18 | **W5.5 回归 fixture 热修收官**："
        "`stock-radar-fixture-{sec-block,score-low,score-high}`；**524 tests** |\n\n"
    )
    cl_marker = "| 2026-06-16 | **W5.5 安全 gate"
    if "2026-06-17 | **执行层路线重定向" not in text:
        text = text.replace(cl_marker, changelog + cl_marker)

    return text


def _summary(text: str) -> None:
    lines = text.splitlines()
    moji = sum(1 for c in text if c in "鎬昏处鏂囨")
    print(f"restored RECORD preview ({len(lines)} lines, mojibake_sample={moji})", file=sys.stderr)
    for line in lines[:3]:
        print(line[:100], file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Incident recovery: rebuild RECORD.md from git "
            f"{BASE_COMMIT} + W8 patches. Not for daily updates."
        )
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Overwrite RECORD.md in the repo root (destructive)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write restored content to this file instead of stdout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary to stderr only; do not write (default without --write/--output)",
    )
    args = parser.parse_args(argv)

    text = restore_record_text()

    if args.write and args.output:
        print("use either --write or --output, not both", file=sys.stderr)
        return 2

    if args.write:
        out = ROOT / "RECORD.md"
        out.write_text(text, encoding="utf-8", newline="\n")
        _summary(text)
        print(f"wrote {out}", file=sys.stderr)
        return 0

    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
        _summary(text)
        print(f"wrote {args.output}", file=sys.stderr)
        return 0

    if args.dry_run:
        _summary(text)
        return 0

    # Default: dry-run style summary (no write)
    _summary(text)
    print("no file written; use --output PATH or --write to save", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
