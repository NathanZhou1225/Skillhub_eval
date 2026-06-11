from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillhub_eval.core.chat_notifications import (
    compute_case_gate,
    compute_gap_zero,
)
from skillhub_eval.core.confirm_lexicon import is_draft_confirm_message
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.schemas.enums import BundleState
from skillhub_eval.providers.base import BaseLLMProvider
from skillhub_eval.settings import settings

from .gaps import scan_gaps

_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)

_OPENING_MARKER = "__TRIGGER_AGENT_OPENING__"
_CONFIRM_ALL_MARKER = "__SYSTEM_ACTION_CONFIRM_ALL__"

_DRAFT_CONFIRM_PREFIXES = (
    "按这个补",
)


_UI_S2_CLARIFY_RULE = (
    "当 Skill 设计意图、用途、受众、输出形态等不确定时，intent 必须是 clarify，"
    "patch 必须为 null，禁止 mutation"
)


@dataclass
class LuiResponse:
    intent: str
    reply: str
    patch: dict | None
    clarification_keys: list[str] | None = None


class LuiAgent:
    def __init__(self, ds_provider: BaseLLMProvider):
        self.ds_provider = ds_provider

    async def respond(
        self,
        conversation_id: str,
        user_message: str,
        history: list[dict],
        report: dict | None,
        conv: dict,
        repo: Repository,
        staging_path: Path | None = None,
    ) -> LuiResponse:
        if conv.get("status") == "frozen":
            return LuiResponse(
                intent="explain_only",
                reply=self._frozen_explain(report),
                patch=None,
            )

        if user_message == _OPENING_MARKER:
            return await self._handle_opening(conversation_id, report, repo)
        if user_message == _CONFIRM_ALL_MARKER:
            return await self._handle_confirm_all(conversation_id, repo, staging_path)

        if conv.get("status") == "awaiting_draft_confirm":
            return await self._handle_awaiting_draft_confirm(
                conversation_id=conversation_id,
                user_message=user_message,
                history=history,
                report=report,
                repo=repo,
                staging_path=staging_path,
            )

        return await self._llm_respond(
            conversation_id, user_message, history, report, repo, staging_path
        )

    async def _handle_opening(
        self,
        conversation_id: str,
        report: dict | None,
        repo: Repository,
    ) -> LuiResponse:
        messages = repo.get_lui_messages(conversation_id)
        if any(m.get("role") == "agent" for m in messages):
            return LuiResponse(intent="system_action", reply="", patch=None)

        opening = self._compose_opening(report)
        repo.append_lui_message(conversation_id, role="agent", content=opening)
        return LuiResponse(intent="system_action", reply=opening, patch=None)

    async def _handle_confirm_all(
        self,
        conversation_id: str,
        repo: Repository,
        staging_path: Path | None,
    ) -> LuiResponse:
        if staging_path is None:
            return LuiResponse(
                intent="explain_only",
                reply="当前会话缺少 staging 路径，暂时无法执行整包确认。",
                patch=None,
            )

        bundle = ingest_bundle(str(staging_path))
        gaps = scan_gaps(bundle, BundleState.draft_enriched)
        required_gaps = [
            g for g in gaps.get("gaps", []) if g.get("severity") == "required"
        ]
        if required_gaps:
            return LuiResponse(
                intent="explain_only",
                reply=f"仍有 {len(required_gaps)} 个必填缺口未补齐，暂时无法确认整包。",
                patch=None,
            )

        repo.set_conversation_auto_confirmed(conversation_id, True)
        return LuiResponse(
            intent="system_action",
            reply="✅ 整包已确认，系统将发起正式评估。",
            patch=None,
        )

    async def _llm_respond(
        self,
        conversation_id: str,
        user_message: str,
        history: list[dict],
        report: dict | None,
        repo: Repository,
        staging_path: Path | None = None,
    ) -> LuiResponse:
        clarifications = repo.get_clarifications(conversation_id) or {}
        skill_excerpt = ""
        plan_hint = ""
        if staging_path and staging_path.is_dir():
            try:
                bundle = ingest_bundle(str(staging_path))
                skill_excerpt = str(bundle.get("skill_md_text") or "")[:2000]
            except Exception:
                pass
        enrichment = repo.get_plan_enrichment(conversation_id)
        if enrichment:
            plan_hint = json.dumps(enrichment, ensure_ascii=False, default=str)
        prompt = self._build_prompt(
            user_message, history, report,
            clarifications=clarifications,
            skill_excerpt=skill_excerpt,
            plan_hint=plan_hint,
        )
        try:
            raw = await self.ds_provider.judge(prompt)
            payload = self._parse_payload(raw)
            intent = str(payload.get("intent", "explain_only")).strip()
            reply = str(payload.get("reply", "")).strip() or "我先为你解释当前状态。"

            if intent == "clarify":
                return LuiResponse(
                    intent="clarify",
                    reply=reply,
                    patch=None,
                    clarification_keys=self._extract_clarification_keys(payload),
                )

            if intent == "mutation":
                patch = self._sanitize_patch(payload.get("patch"))
                if patch is None:
                    return LuiResponse(intent="explain_only", reply=reply, patch=None)
                return LuiResponse(intent="mutation", reply=reply, patch=patch)

            return LuiResponse(intent="explain_only", reply=reply, patch=None)
        except Exception:
            return LuiResponse(
                intent="explain_only",
                reply="我暂时无法稳定解析这次请求，先为你做解释说明，不会改动文件。",
                patch=None,
            )

    @staticmethod
    def _extract_clarification_keys(payload: dict) -> list[str] | None:
        keys = payload.get("clarification_keys")
        if not isinstance(keys, list):
            return None
        cleaned = [str(k).strip() for k in keys if str(k).strip()]
        return cleaned or None

    def _build_prompt(
        self,
        user_message: str,
        history: list[dict],
        report: dict | None,
        *,
        clarifications: dict | None = None,
        skill_excerpt: str = "",
        plan_hint: str = "",
    ) -> str:
        report_obj = report or {}
        summary_json = json.dumps(
            report_obj.get("skill_summary", {}), ensure_ascii=False, default=str
        )
        gaps_json = json.dumps(report_obj.get("gaps", []), ensure_ascii=False, default=str)
        history_json = json.dumps(history[-8:], ensure_ascii=False, default=str)
        security_status = str(report_obj.get("security_status", "unknown"))
        clarifications_json = json.dumps(
            clarifications or {}, ensure_ascii=False, default=str
        )

        return (
            "你是 SkillHub 作者助手，请帮助用户理解并改进 Skill。\n"
            "输出必须是单个 JSON 对象，不允许 markdown 代码块。\n"
            '格式: {"intent":"explain_only|mutation|clarify","reply":"...",'
            '"patch":null或对象,"clarification_keys":[]}\n'
            "规则:\n"
            "1) reply 必须是简洁中文，不超过400字。\n"
            "2) intent=explain_only 时 patch 必须为 null。\n"
            "3) intent=mutation 时 patch 仅允许 skill_md_updates 和 eval_cases 两个键。\n"
            "4) patch 严禁包含 sample_io。\n"
            "5) 用户只是提问/解释诉求时，intent 必须是 explain_only。\n"
            f"6) {_UI_S2_CLARIFY_RULE}。\n"
            "7) intent=clarify 时 patch 必须为 null，clarification_keys 可选列出待澄清字段 key。\n"
            "8) 全对话生命周期均适用上述 clarify 规则，不仅限于补题阶段。\n"
            "9) 对用户说「评估条件/评估需求」，避免只说「题型」。\n\n"
            f"安全状态: {security_status}\n"
            f"技能摘要: {summary_json}\n"
            f"缺口列表: {gaps_json}\n"
            f"已有澄清: {clarifications_json}\n"
            f"补题/enrich 上下文: {plan_hint}\n"
            f"SKILL 摘录: {skill_excerpt}\n"
            f"历史消息: {history_json}\n"
            f"用户消息: {user_message}\n"
        )

    def _parse_payload(self, raw: Any) -> dict:
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            raise ValueError("unsupported response type")
        text = raw.strip()
        fenced = _MD_FENCE_RE.match(text)
        if fenced:
            text = fenced.group(1).strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("parsed payload is not object")
        return parsed

    def _sanitize_patch(self, patch: Any) -> dict | None:
        if not isinstance(patch, dict):
            return None
        sanitized: dict[str, Any] = {}
        if isinstance(patch.get("skill_md_updates"), dict):
            sanitized["skill_md_updates"] = patch["skill_md_updates"]
        if isinstance(patch.get("eval_cases"), list):
            sanitized["eval_cases"] = patch["eval_cases"]
        # Explicitly drop sample_io even if model returns it.
        return sanitized if sanitized else None

    def _frozen_explain(self, report: dict | None) -> str:
        summary = (report or {}).get("skill_summary") or {}
        weaknesses = self._to_text(summary.get("weaknesses"), "待专家复核")
        return (
            "当前会话已进入专家复核冻结状态，暂不能继续自动改写。"
            f"你可先查看不足点：{weaknesses}"
        )

    def _compose_opening(self, report: dict | None) -> str:
        report_obj = report or {}
        summary = report_obj.get("skill_summary") or {}
        highlights = self._to_text(summary.get("highlights"), "暂无亮点摘要")
        weaknesses = self._to_text(summary.get("weaknesses"), "暂无不足摘要")
        security_status = str(report_obj.get("security_status", "unknown"))

        gaps = report_obj.get("gaps") or []
        required_count = sum(
            1 for gap in gaps if isinstance(gap, dict) and gap.get("severity") == "required"
        )

        lines = [
            "你好！我已完成对你的 Skill 初步扫描。",
            f"📊 亮点：{highlights}",
            f"⚠️ 不足：{weaknesses}",
        ]
        if security_status != "passed":
            lines.append(f"🔒 安全状态提示：{security_status}")
        if required_count > 0:
            lines.append(f"📋 发现 {required_count} 个必填缺口，我可以帮你逐项补全。")
        else:
            lines.append("✅ 基础结构已完整。")
        return "\n".join(lines)

    def _to_text(self, value: Any, default: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            items = [str(x).strip() for x in value if str(x).strip()]
            if items:
                return "；".join(items[:3])
        return default

    @staticmethod
    def is_draft_confirmation(message: str) -> bool:
        if is_draft_confirm_message(message):
            return True
        lowered = message.strip().lower()
        return any(
            lowered.startswith(prefix) for prefix in _DRAFT_CONFIRM_PREFIXES
        )

    def _build_draft_preview_payload(self, patch: dict, staging_path: Path | None) -> dict:
        files: list[str] = []
        cases_preview: list[dict] = []
        updates = patch.get("skill_md_updates")
        if isinstance(updates, dict) and updates:
            files.append("SKILL.md (frontmatter)")
        cases = patch.get("eval_cases")
        if isinstance(cases, list):
            for idx, case in enumerate(cases):
                if not isinstance(case, dict):
                    continue
                case_id = str(case.get("id") or f"lui_draft_{idx + 1}")
                files.append(f"eval_cases/{case_id}.yaml")
                files.append(f"sample_io/{case_id}.json")
                cases_preview.append(
                    {
                        "id": case_id,
                        "type": case.get("type", ""),
                        "user_intent": case.get("user_intent", ""),
                        "input_snippet": str(case.get("input_template", ""))[:120],
                    }
                )
        return {
            "files_to_write": files,
            "cases_preview": cases_preview,
            "skill_md_updates": updates if isinstance(updates, dict) else {},
            "flow_step": {"current": 3, "total": 3, "label_zh": "确认写入草案"},
            "next_hint_zh": "确认后将写入练习区并重新初评；也可继续描述修改意见。",
        }

    async def _publish_draft_preview(
        self,
        conversation_id: str,
        repo: Repository,
        draft: dict,
        staging_path: Path | None,
    ) -> None:
        patch = draft.get("patch") if isinstance(draft.get("patch"), dict) else {}
        narrative = str(draft.get("reply", "")).strip() or (
            "初评已完成，我已根据缺口生成修改草案，请确认后我再写入。"
        )
        if patch:
            repo.set_pending_patch(conversation_id, patch)
            preview = self._build_draft_preview_payload(patch, staging_path)
            repo.append_lui_message(
                conversation_id,
                role="agent",
                content="",
                message_type="draft_preview",
                payload_json=preview,
            )
        repo.append_lui_message(conversation_id, role="agent", content=narrative)

    async def generate_draft_for_staging(
        self,
        staging_path: Path | None,
        repo: Repository,
        conversation_id: str,
    ) -> dict:
        conv = repo.get_conversation(conversation_id) or {}
        report = None
        if conv.get("active_run_id"):
            report = repo.get_report(str(conv["active_run_id"]))
        path = staging_path or Path(".")
        draft = await self._generate_draft_patch(report, path, force_cases=True)
        await self._publish_draft_preview(conversation_id, repo, draft, staging_path)
        return draft

    @staticmethod
    def _resolve_staging_path(conversation_id: str, conv: dict, run: dict | None) -> Path:
        if run and run.get("skill_bundle_path"):
            return Path(str(run["skill_bundle_path"]))
        if conv.get("source_path"):
            return Path(str(conv["source_path"]))
        return Path(settings.staging_root) / conversation_id

    @classmethod
    def compose_post_initial_narrative_template(
        cls,
        conversation_id: str,
        run_id: str,
        repo: Repository,
    ) -> str:
        run = repo.get_run(run_id) or {}
        conv = repo.get_conversation(conversation_id) or {}
        staging_path = cls._resolve_staging_path(conversation_id, conv, run)
        report = repo.get_report(run_id) or {}

        gap_zero = False
        case_gate_passed = False
        try:
            gap_zero = compute_gap_zero(staging_path)
            case_gate_passed = bool(compute_case_gate(staging_path).get("passed"))
        except Exception:
            pass

        if gap_zero and case_gate_passed:
            narrative = (
                "初评体检已完成。请查看下方「初评就绪」卡片："
                "可先处理可选改进，或直接点「开始正式评估」进入双模型评审。"
            )
            repo.append_lui_message(conversation_id, role="agent", content=narrative)
            return narrative

        if not gap_zero:
            gaps = (report.get("gaps") or []) if report else []
            blocking = [
                g for g in gaps
                if isinstance(g, dict) and g.get("severity") in ("required", "block")
            ]
            lines = [
                "初评已完成。以下字段仍需补全：",
            ]
            for gap in blocking[:5]:
                field = gap.get("field_path", "")
                msg = gap.get("message", "")
                lines.append(f"· {field}：{msg}")
            lines.append("我已准备好修改草案，请确认后我再写入。")
            narrative = "\n".join(lines)
            repo.append_lui_message(conversation_id, role="agent", content=narrative)
            return narrative

        narrative = (
            "字段已基本齐全，但评测题型仍在补充或数量不足。"
            "请按建议补全后再进入正式评估。"
        )
        repo.append_lui_message(conversation_id, role="agent", content=narrative)
        return narrative

    @classmethod
    def compose_post_formal_narrative_template(cls, run_id: str, repo: Repository) -> str:
        run = repo.get_run(run_id) or {}
        report = repo.get_report(run_id) or {}
        summary = (report or {}).get("skill_summary") or {}
        highlights = cls._to_text_static(summary.get("highlights"), "质量评估已完成")
        score = run.get("score_total")
        score_line = (
            f"综合得分 {float(score):.1f}。"
            if score is not None
            else ""
        )
        return (
            f"正式评估已完成。{score_line}"
            f"亮点：{highlights}。"
            "点击简卡中的「查看完整报告」可在历史详情查看全量内容。"
        )

    @staticmethod
    def _to_text_static(value: Any, default: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            items = [str(x).strip() for x in value if str(x).strip()]
            if items:
                return "；".join(items[:3])
        return default

    async def compose_post_formal_narrative(self, run_id: str, repo: Repository) -> str:
        return self.compose_post_formal_narrative_template(run_id, repo)

    async def handle_post_initial_review(
        self,
        conversation_id: str,
        run_id: str,
        repo: Repository,
    ) -> None:
        run = repo.get_run(run_id) or {}
        conv = repo.get_conversation(conversation_id) or {}
        staging_path = self._resolve_staging_path(conversation_id, conv, run)
        report = repo.get_report(run_id) or {}

        gap_zero = False
        case_gate_passed = False
        try:
            gap_zero = compute_gap_zero(staging_path)
            case_gate_passed = bool(compute_case_gate(staging_path).get("passed"))
        except Exception:
            pass

        if gap_zero and case_gate_passed:
            narrative = (
                "初评体检已完成。请查看下方「初评就绪」卡片："
                "可先处理可选改进，或直接点「开始正式评估」进入双模型评审。"
            )
            repo.append_lui_message(conversation_id, role="agent", content=narrative)
            return

        if not gap_zero:
            draft = await self._generate_draft_patch(report, staging_path, force_cases=True)
            await self._publish_draft_preview(conversation_id, repo, draft, staging_path)
            repo.update_conversation_status(conversation_id, "awaiting_draft_confirm")
            return

        narrative = (
            "字段已基本齐全，但评测题型仍在补充或数量不足。"
            "请按建议补全后再进入正式评估。"
        )
        repo.append_lui_message(conversation_id, role="agent", content=narrative)

    async def _generate_draft_patch(
        self,
        report: dict | None,
        staging_path: Path,
        *,
        force_cases: bool = False,
    ) -> dict:
        gaps_json = json.dumps((report or {}).get("gaps", []), ensure_ascii=False)
        excerpt = ""
        if staging_path.is_dir():
            try:
                excerpt = str(ingest_bundle(str(staging_path)).get("skill_md_text") or "")[:2000]
            except Exception:
                pass
        force_line = (
            "4) 若缺口含 eval_cases 或目录缺失，patch.eval_cases 至少 1 条，含 type/user_intent/input_template/expected_behavior。\n"
            if force_cases
            else ""
        )
        prompt = (
            "你是 SkillHub 作者助手。初评发现评估条件缺口，请生成白话说明和修改草案。\n"
            "输出必须是单个 JSON 对象，不允许 markdown 代码块。\n"
            '格式: {"reply":"白话说明含将写入什么文件","patch":{"skill_md_updates":{...},"eval_cases":[]}}\n'
            "规则:\n"
            "1) reply 用「初评」称呼，说明下一步点「确认写入」。\n"
            "2) patch 仅允许 skill_md_updates 和 eval_cases。\n"
            "3) 不要说可以正式评估。\n"
            f"{force_line}"
            f"缺口列表: {gaps_json}\n"
            f"SKILL 摘录: {excerpt}\n"
        )
        try:
            raw = await self.ds_provider.judge(prompt)
            payload = self._parse_payload(raw)
            reply = str(payload.get("reply", "")).strip()
            patch = self._sanitize_patch(payload.get("patch"))
            return {"reply": reply, "patch": patch or {}}
        except Exception:
            return {
                "reply": "初评已完成，我已根据缺口生成修改草案，请确认后我再写入。",
                "patch": {},
            }

    def _append_draft_failed(self, conversation_id: str, repo: Repository) -> None:
        repo.append_lui_message(
            conversation_id,
            role="agent",
            content="自动生成草案未成功。你可以：再试一次、手动上传 ZIP，或切到自动出题。",
            message_type="draft_failed",
            payload_json={
                "next_hint_zh": "请选择下方按钮继续。",
                "actions": ["retry", "manual_upload", "propagate"],
            },
        )

    async def _handle_awaiting_draft_confirm(
        self,
        conversation_id: str,
        user_message: str,
        history: list[dict],
        report: dict | None,
        repo: Repository,
        staging_path: Path | None,
    ) -> LuiResponse:
        if self.is_draft_confirmation(user_message) or user_message.strip() == "__ACTION_DRAFT_CONFIRM__":
            pending = repo.get_pending_patch(conversation_id)
            if not pending:
                return LuiResponse(
                    intent="explain_only",
                    reply="当前没有待确认的草案，请先让我生成修改建议。",
                    patch=None,
                )
            return LuiResponse(
                intent="mutation",
                reply="好的，正在按草案写入并重新初评。",
                patch=pending,
            )

        clarifications = repo.get_clarifications(conversation_id) or {}
        failures = int(clarifications.get("_draft_failures", 0))
        force = failures > 0 or any(
            p in user_message for p in ("直接帮我", "你帮我写", "你帮我补充")
        )
        draft = await self._generate_draft_patch(
            report,
            staging_path or Path("."),
            force_cases=force,
        )
        patch = draft.get("patch") if isinstance(draft.get("patch"), dict) else {}
        if not patch:
            failures += 1
            repo.merge_clarifications(conversation_id, {"_draft_failures": str(failures)})
            if failures >= 2:
                self._append_draft_failed(conversation_id, repo)
                return LuiResponse(
                    intent="explain_only",
                    reply="自动生成仍未成功，请选下方按钮继续。",
                    patch=None,
                )
        await self._publish_draft_preview(conversation_id, repo, draft, staging_path)
        narrative = str(draft.get("reply", "")).strip() or "我已根据你的意见更新草案，请确认后我再写入。"
        return LuiResponse(intent="explain_only", reply=narrative, patch=None)
