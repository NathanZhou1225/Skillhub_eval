# Design: Wave 4 — LUI Agent + 对话/卡片 UI

> 实现参考文档。Subagent 执行前必须读本文件；接口定义即合约，不允许 TBD。

---

## 0. 系统常量与 DB 迁移

### 0.1 RUNNING_STATUSES（新增到 enums.py）

```python
# skillhub_eval/core/schemas/enums.py
RUNNING_STATUSES: frozenset[str] = frozenset({
    "pending", "level0_checking", "risk_locking", "normalizing",
    "case_executing", "code_asserting", "model_judging", "aggregating",
})
```

### 0.2 conversations 表 migration（SCHEMA_VERSION → 2）

新增两列（grill-me G1 + G4 决断）：
- `auto_confirmed INTEGER NOT NULL DEFAULT 0` — 用户点【整包确认】后置 1；mutation 后重置为 0
- `source_path TEXT` — 用户原始文件路径（local_ref 存原始目录；upload 存 `data/originals/{conv_id}/`）；W6 listing 发布时从此路径复制，**不从 staging 复制**

在 `sqlite.py init_db()` 的版本门控中追加：

```python
if version < 2:
    existing_cols = {r[1] for r in cursor.execute(
        "PRAGMA table_info('conversations')"
    ).fetchall()}
    for col, typedef in [
        ("auto_confirmed", "INTEGER NOT NULL DEFAULT 0"),
        ("source_path",    "TEXT"),
    ]:
        if col not in existing_cols:
            cursor.execute(
                f"ALTER TABLE conversations ADD COLUMN {col} {typedef}"
            )
    cursor.execute("PRAGMA user_version = 2")
```

**ZIP 上传双目录隔离（grill-me G1）**：

```
data/originals/{conv_id}/   ← 解压 zip 原始文件（只读，W6 listing 来源）
data/staging/{conv_id}/     ← copy from originals，供 LUI 代写
```

`create_conversation` 方法新增 `source_path: str = ""` 参数并存入 DB。

### 0.3 新增 Port 方法（core/ports.py）

```python
def increment_auto_run_count(self, conversation_id: str) -> int: ...
# 原子 +1，返回新值；实现：UPDATE ... SET auto_run_count = auto_run_count + 1

def reset_auto_run_count(self, conversation_id: str) -> None: ...
# UPDATE ... SET auto_run_count = 0

def set_conversation_auto_confirmed(self, conversation_id: str, value: bool) -> None: ...
# UPDATE ... SET auto_confirmed = ?

def supersede_run(self, old_run_id: str, new_run_id: str) -> None: ...
# UPDATE evaluation_runs SET status='superseded', superseded_by_run_id=? WHERE run_id=?
# 注意：不更新 conversations.active_run_id（create_run 已原子更新）

def get_lui_messages(self, conversation_id: str) -> list[dict]: ...
# SELECT * FROM lui_messages WHERE conversation_id=? ORDER BY created_at

def create_conversation(
    self, skill_id: str, source: str,
    max_auto_runs: int = 5, source_path: str = ""
) -> str: ...
# 签名扩展：source_path 存入 DB（grill-me G1）
```

---

## 1. Session Gate（adapters/api/_session.py 新建）

```python
from fastapi import HTTPException
from skillhub_eval.core.schemas.enums import RUNNING_STATUSES
from skillhub_eval.core.ports import Repository

def check_session_gate(conversation_id: str, repo: Repository) -> None:
    """
    Raises:
      403 ConversationFrozenError  — conversation.status == 'frozen'
      409 SessionLockedError       — active_run.status in RUNNING_STATUSES
    """
    conv = repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.get("status") == "frozen":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CONVERSATION_FROZEN",
                "message": "当前 Skill 正在等待专家审核，暂时无法修改。"
                           "专家驳回后将自动解冻。",
            },
        )

    active_run_id = conv.get("active_run_id")
    if active_run_id:
        run = repo.get_run(active_run_id)
        if run and run.get("status") in RUNNING_STATUSES:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "SESSION_LOCKED",
                    "message": "评估引擎正在运行，请稍候再试。",
                    "active_run_id": active_run_id,
                },
            )
```

---

## 2. core/lui_agent.py

### 2.1 接口

```python
@dataclass
class LuiResponse:
    intent: str          # "explain_only" | "mutation" | "system_action"
    reply: str           # 中文回复文本
    patch: dict | None   # 仅 mutation 时非 null

class LuiAgent:
    def __init__(self, ds_provider: BaseLLMProvider): ...

    async def generate_opening(
        self,
        conversation_id: str,
        report: dict,
        repo: Repository,
    ) -> None:
        """生成开场白并写入 lui_messages(role=agent)"""

    async def respond(
        self,
        conversation_id: str,
        user_message: str,
        history: list[dict],   # [{role, content}]
        report: dict | None,
        conv: dict,
        repo: Repository,
    ) -> LuiResponse:
```

### 2.2 特殊 Marker 拦截（不过 LLM）

**幂等保护（grill-me 实现修正）**：`__TRIGGER_AGENT_OPENING__` 到达时，先检查 `lui_messages` 是否已有 `role=agent` 的消息；若有则静默忽略（返回空 reply），防止 UI 3s 轮询重复触发。

```python
SYSTEM_MARKERS = {
    "__TRIGGER_AGENT_OPENING__": "_handle_opening",
    "__SYSTEM_ACTION_CONFIRM_ALL__": "_handle_confirm_all",
}

async def respond(self, ...) -> LuiResponse:
    # 1. Frozen check → 强制 explain_only
    if conv.get("status") == "frozen":
        return LuiResponse(intent="explain_only",
                           reply=self._frozen_explain(report), patch=None)

    # 2. Special marker 精确字符串匹配
    if user_message in SYSTEM_MARKERS:
        handler = getattr(self, SYSTEM_MARKERS[user_message])
        return await handler(conversation_id, report, conv, repo)

    # 3. 普通消息 → LLM 单次结构化调用
    return await self._llm_respond(user_message, history, report, conv)
```

### 2.3 LLM System Prompt 框架

```
你是 SkillHub 作者助手，帮助非技术用户理解和改善他们上传的 Skill。

当前 Skill 评估摘要：
{skill_summary}

缺口列表（gap）：
{gaps_json}

安全状态：{security_status}

规则：
1. 必须输出有效 JSON，格式严格如下：
   {"intent": "<explain_only|mutation>", "reply": "<中文回复>", "patch": <null或见下>}
2. patch 格式（仅 mutation 时填写）：
   {
     "skill_md_updates": {"field_name": "value"},
     "eval_cases": [{"type": "...", "user_intent": "...", "input_template": "...", "expected_behavior": "..."}],
     "sample_io": [{"case_id": "...", "input": "...", "output": "..."}]
   }
3. SKILL.md 的 patch 只能包含 frontmatter 字段（如 category、negative_prompts、returns_schema），
   不得包含 body 内容。
4. 如果用户只是问问题或寻求解释，intent=explain_only，patch=null。
5. 回复语言：简洁中文，面向非技术用户，不超过 200 字。
```

### 2.4 `__SYSTEM_ACTION_CONFIRM_ALL__` 处理

```python
async def _handle_confirm_all(self, conv_id, report, conv, repo) -> LuiResponse:
    # 前置检查：gap 是否真的归零
    # grill-me 修正：使用 BundleState.draft_enriched（暴露所有真实缺口，不提前用 confirmed 状态）
    staging_path = ...  # 从 conv["source_path"] or settings.staging_root + conv_id 解析
    bundle = ingest_bundle(str(staging_path))
    gaps = scan_gaps(bundle, BundleState.draft_enriched)  # 明确指定
    required_gaps = [g for g in gaps.get("gaps", []) if g.get("severity") == "required"]

    if required_gaps:
        return LuiResponse(
            intent="explain_only",
            reply=f"仍有 {len(required_gaps)} 个必填缺口未补齐，暂时无法确认整包。缺口：{[g['field'] for g in required_gaps[:3]]}",
            patch=None,
        )

    repo.set_conversation_auto_confirmed(conv_id, True)
    return LuiResponse(
        intent="system_action",
        reply="✅ 整包已确认！系统将发起正式全量评估，请稍候...",
        patch=None,
    )
```

### 2.5 开场白生成（`__TRIGGER_AGENT_OPENING__`）

```python
async def generate_opening(self, conv_id, report, repo) -> None:
    summary = report.get("skill_summary", {})
    gaps = report.get("gaps", [])
    required_count = sum(1 for g in gaps if g.get("severity") == "required")
    security = report.get("security_status", "passed")

    opening = self._compose_opening(summary, required_count, security)
    repo.append_lui_message(conv_id, role="agent", content=opening)
```

开场白模板（确定性拼装，不调 LLM，避免等待）：

```
你好！我已完成对你的 Skill 的初步扫描。

📊 亮点：{highlights}
⚠️ 不足：{weaknesses}
{'🔒 安全提示：检测到 ' + security_warning if security != "passed" else ''}

{'📋 发现 ' + str(required_count) + ' 个必填缺口，我可以帮你补全。' if required_count > 0 else '✅ 基础结构完整！'}

你可以直接告诉我：
- "帮我补 adversarial case"
- "解释一下为什么分数低"
- "帮我写 negative_prompts"
```

---

## 3. core/staging_writer.py

### 3.1 接口

```python
@dataclass
class WriterResult:
    files_written: list[str]   # 写入的文件相对路径
    hash_changed: bool          # staging 内容是否有实质变化

class StagingWriter:
    def __init__(self, repo: Repository): ...

    def apply_patch(self, staging_path: Path, patch: dict) -> WriterResult: ...
    def compute_next_run_mode(
        self, staging_path: Path, conv: dict
    ) -> tuple[EvaluationMode, BundleState]: ...
    async def trigger_next_run(
        self,
        conv_id: str,
        old_run_id: str,
        staging_path: Path,
        skill_id: str,
        ds_provider: BaseLLMProvider,
        gemini_provider: BaseLLMProvider,
        background_tasks: BackgroundTasks,
    ) -> str | None:
        """返回 new_run_id，或 None（quota 熔断时）"""
```

### 3.2 apply_patch 详细逻辑

**SKILL.md frontmatter patch（严格保护 body）**：

```python
def _patch_skill_md(self, staging_path: Path, updates: dict) -> bool:
    skill_md = staging_path / "SKILL.md"
    if not skill_md.exists():
        return False

    content = skill_md.read_text(encoding="utf-8")

    # 分离 frontmatter 和 body
    if content.startswith("---"):
        parts = content.split("---", 2)
        # parts[0] = "" (before first ---), parts[1] = frontmatter yaml, parts[2] = body
        if len(parts) >= 3:
            import yaml
            fm = yaml.safe_load(parts[1]) or {}
            fm.update(updates)  # Upsert frontmatter keys
            body = parts[2]
            new_content = f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---{body}"
            skill_md.write_text(new_content, encoding="utf-8")
            return True

    return False  # 无 frontmatter → 跳过
```

**eval_cases 写入**（复用 Propagator._write_case 格式，id 由服务端分配）：

```python
def _write_cases(self, staging_path: Path, cases: list[dict]) -> list[str]:
    written = []
    # 先统计现有 writer 写的 case 数量，避免 ID 冲突
    existing = list((staging_path / "eval_cases").glob("lui_*.yaml"))
    start_idx = len(existing)
    for i, case in enumerate(cases):
        case_type = case.get("type", "happy_path")
        abbr = {"happy_path": "hp", "edge": "ec", "refusal": "rf", "adversarial": "adv"}.get(case_type, case_type)
        case_id = f"lui_{abbr}_{start_idx + i:02d}"
        yaml_data = {
            "id": case_id,
            "type": case_type,
            "origin": "lui_agent",
            "user_intent": case.get("user_intent", ""),
            "input_template": case.get("input_template", ""),
            "expected_behavior": case.get("expected_behavior", ""),
        }
        yaml_path = staging_path / "eval_cases" / f"{case_id}.yaml"
        yaml_path.write_text(yaml.dump(yaml_data, allow_unicode=True), encoding="utf-8")
        json_path = staging_path / "sample_io" / f"{case_id}.json"
        json_path.write_text(json.dumps({"input": "", "output": None}), encoding="utf-8")
        written.append(f"eval_cases/{case_id}.yaml")
    return written
```

### 3.3 compute_next_run_mode

```python
def compute_next_run_mode(
    self, staging_path: Path, conv: dict
) -> tuple[EvaluationMode, BundleState]:
    bundle = ingest_bundle(str(staging_path))
    gate = Level0Checker().check_case_gate(bundle)
    gaps = scan_gaps(bundle, BundleState.draft_enriched)
    required_gaps = [g for g in gaps.get("gaps", []) if g.get("severity") == "required"]

    # 路由 A：题型或数量未完整
    if not gate["passed"]:
        return EvaluationMode.degraded, BundleState.minimal

    # 路由 B：题型完整但 metadata gap 未归零
    if required_gaps:
        return EvaluationMode.degraded, BundleState.draft_enriched

    # 路由 C：题型完整 + gap 归零 + 用户已点【整包确认】
    if conv.get("auto_confirmed"):
        return EvaluationMode.capability_full, BundleState.confirmed

    # 题型完整 + gap 归零 + 尚未确认 → 仍 degraded（等用户点确认按钮）
    return EvaluationMode.degraded, BundleState.draft_enriched
```

### 3.4 trigger_next_run（含 quota 熔断）

```python
async def trigger_next_run(self, conv_id, old_run_id, staging_path,
                            skill_id, ds, gemini, background_tasks) -> str | None:
    conv = self.repo.get_conversation(conv_id)

    # Quota 检查（先读不加）
    if conv["auto_run_count"] >= conv["max_auto_runs"]:
        self._freeze_and_escalate(conv_id, old_run_id)
        return None

    # 原子递增
    new_count = self.repo.increment_auto_run_count(conv_id)

    # 复评路由
    eval_mode, bundle_state = self.compute_next_run_mode(staging_path, conv)

    # 创建新 run（原子回写 conversations.active_run_id）
    new_run_id = self.repo.create_run(
        skill_id=skill_id,
        skill_bundle_path=str(staging_path),
        bundle_state=bundle_state.value,
        evaluation_mode=eval_mode.value,
        conversation_id=conv_id,
        parent_run_id=old_run_id,
    )
    # grill-me 修正：单步 supersede（create_run 已原子更新 active_run_id，
    # 无需 "__pending__" 占位两步；supersede_run 只更新旧 run 的字段）
    self.repo.supersede_run(old_run_id, new_run_id)

    # 启动评估
    from skillhub_eval.core.engine import EvaluationEngine
    engine = EvaluationEngine(repo=self.repo, ds_provider=ds, wb_provider=gemini)
    background_tasks.add_task(
        engine.run_async,
        run_id=new_run_id,
        skill_bundle_path=str(staging_path),
        bundle_state=bundle_state,
        evaluation_mode=eval_mode,
    )

    return new_run_id

def _freeze_and_escalate(self, conv_id: str, active_run_id: str) -> None:
    self.repo.set_human_review_required(
        active_run_id, True, ["CONVERSATION_QUOTA_EXCEEDED"]
    )
    self.repo.update_status(active_run_id, "awaiting_human_review")
    self.repo.update_conversation_status(conv_id, "frozen")
    self.repo.append_lui_message(
        conv_id, role="agent",
        content=(
            "⛔ 已达到本轮最大自动修改次数（5 次）。\n"
            "系统已通知专家介入，请等待专家审核。\n"
            "专家驳回后，你将获得新的 5 次修改机会。"
        ),
    )
```

---

## 4. API 路由

### 4.1 POST /conversations/{conv_id}/chat

```python
class ChatRequest(BaseModel):
    message: str
    run_id: str | None = None   # 前端可传当前轮询的 run_id 用于 report 拉取

class ChatResponse(BaseModel):
    reply: str
    intent: str
    new_run_id: str | None = None
    auto_confirmed: bool = False
    gap_zero: bool = False      # 前端用于决定是否显示【整包确认】按钮
```

**执行流程**：

```
check_session_gate(conv_id, repo)         → 403 frozen / 409 running / pass
append_lui_message(user, message)
拉取 report（active_run_id）
lui_agent.respond(conv_id, message, history, report, conv, repo)
append_lui_message(agent, reply)

if intent == "mutation":
    writer_result = staging_writer.apply_patch(staging_path, patch)
    if writer_result.hash_changed:
        # grill-me G4：staging 内容改变 → 重置 auto_confirmed
        # 在 /chat 处理器层重置（职责分离：staging_writer 不感知 conv_id）
        repo.set_conversation_auto_confirmed(conv_id, False)
        new_run_id = await staging_writer.trigger_next_run(...)

if intent == "system_action":
    # __SYSTEM_ACTION_CONFIRM_ALL__：lui_agent 已在内部设置 auto_confirmed=True
    # 不重置（这是用户主动确认，auto_confirmed 此时应为 True）
    new_run_id = await staging_writer.trigger_next_run(...)  # 立即触发 capability_full

return ChatResponse(reply, intent, new_run_id, auto_confirmed=conv_post.get("auto_confirmed", False), ...)
```

**auto_confirmed 状态机**：

| 事件 | auto_confirmed |
|------|---------------|
| 系统初始 / mutation + hash_changed | → `False` |
| `__SYSTEM_ACTION_CONFIRM_ALL__` + gap 验证通过 | → `True` |
| Expert Reject | → `False` |
| Expert Approve | 不变（PASS 已完成，W6 负责后续） |

### 4.2 POST /conversations/{conv_id}/confirm-cases（简化版）

```python
class ConfirmCasesRequest(BaseModel):
    case_ids: list[str]

# 仅写 YAML confirmed=true，无 run 触发
for case_id in case_ids:
    yaml_path = staging_path / "eval_cases" / f"{case_id}.yaml"
    data = yaml.safe_load(yaml_path.read_text())
    data["confirmed"] = True
    yaml_path.write_text(yaml.dump(data, allow_unicode=True))
return {"updated": case_ids}
```

Session Lock 仍要检查（防止 engine running 时写 YAML）。

### 4.3 GET /conversations/{conv_id}/messages

```python
return {
    "conversation_id": conv_id,
    "messages": repo.get_lui_messages(conv_id),
    # [{id, role, content, created_at, run_id}]
}
```

### 4.4 GET /conversations/{conv_id}/status

```python
conv = repo.get_conversation(conv_id)
active_run = repo.get_run(conv["active_run_id"]) if conv.get("active_run_id") else None
lui_count = len(repo.get_lui_messages(conv_id))

# gap_zero 计算
staging_path = ...
bundle = ingest_bundle(str(staging_path))
gaps = scan_gaps(bundle, ...)
gap_zero = not any(g.get("severity") == "required" for g in gaps.get("gaps", []))
gate = Level0Checker().check_case_gate(bundle)

return {
    "conversation_id": conv_id,
    "status": conv["status"],
    "active_run_id": conv.get("active_run_id"),
    "run_status": active_run["status"] if active_run else None,
    "auto_run_count": conv["auto_run_count"],
    "max_auto_runs": conv["max_auto_runs"],
    "auto_confirmed": bool(conv.get("auto_confirmed")),
    "lui_messages_count": lui_count,
    "gap_zero": gap_zero,
    "case_gate_passed": gate["passed"],
    "case_type_coverage": gate.get("type_coverage", {}),
}
```

### 4.5 POST /conversations/start — zip 上传支持

```python
from fastapi import File, Form, UploadFile

@router.post("/start", ...)
async def start_conversation(
    skill_id: str = Form(...),
    source: str = Form("local_ref"),
    skill_bundle_path: str = Form(""),
    bundle_zip: UploadFile | None = File(None),
    ...
):
    if bundle_zip is not None:
        # ── zip 上传：双目录隔离（grill-me G1）────────────────────────────────
        # originals_path：只读原始文件（W6 listing 来源）
        # staging_path：可写沙盒（LUI 代写目标）
        originals_path = Path(settings.staging_root).parent / "originals" / conversation_id
        staging_path   = Path(settings.staging_root) / conversation_id
        originals_path.mkdir(parents=True, exist_ok=True)
        staging_path.mkdir(parents=True, exist_ok=True)

        zip_bytes = await bundle_zip.read()
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(originals_path)  # 解压到 originals（只读原始）
        except zipfile.BadZipFile:
            repo.update_conversation_status(conversation_id, "error")
            shutil.rmtree(originals_path, ignore_errors=True)
            raise HTTPException(status_code=422, detail="Invalid zip file")

        # 验证 SKILL.md 存在
        if not (originals_path / "SKILL.md").exists():
            repo.update_conversation_status(conversation_id, "error")
            shutil.rmtree(originals_path, ignore_errors=True)
            raise HTTPException(status_code=422, detail="zip must contain SKILL.md at root")

        # 复制到 staging（可写沙盒）
        shutil.copytree(originals_path, staging_path, dirs_exist_ok=True)
        source_path_str = str(originals_path)  # W6 listing 来源

        conversation_id = repo.create_conversation(
            skill_id=skill_id, source="upload", source_path=source_path_str
        )
    else:
        # local_ref 路径
        source_path_str = skill_bundle_path
        conversation_id = repo.create_conversation(
            skill_id=skill_id, source="local_ref", source_path=source_path_str
        )
        # BundleResolver 做镜像复制（tmp→rename 原子重命名）
        ...
```

**W6 发布时**：`shutil.copytree(conv["source_path"], listings_path)` — 始终从 `source_path` 复制原始文件，绝不从 staging 复制。

### 4.6 POST /eval/review/{run_id} 扩展

在现有 `submit_review` 末尾追加：

```python
# Conversation 联动（仅当 run 有 conversation_id 时）
run = repo.get_run(run_id)
conv_id = run.get("conversation_id")
if conv_id:
    repo.reset_auto_run_count(conv_id)
    if body.action == "reject":
        repo.update_conversation_status(conv_id, "active")   # 解冻
        repo.set_conversation_auto_confirmed(conv_id, False)  # 驳回清除确认
        repo.append_lui_message(
            conv_id,
            role="system",
            content=f"🔓 专家已驳回本次评估。\n驳回意见：{body.comment or '（无）'}\n"
                    "你已获得新的 5 次修改机会，可继续改进 Skill。",
        )
    elif body.action == "approve":
        # approve 不解冻（PASS 后 W6 负责 publish）
        pass
```

---

## 5. UI 改造（adapters/ui/static/index.html）

### 5.1 Tab1 双栏布局

```html
<!-- Tab1: 作者对话 -->
<div id="panel-author" class="flex gap-4 h-full">

  <!-- 左栏：对话面板 (40%) -->
  <div class="w-2/5 flex flex-col bg-white rounded-xl border border-gray-200 shadow-sm">
    <!-- 入口区（首屏，未创建 conversation 时展示） -->
    <div id="conv-entry" class="p-6">
      <h2>开始评估 Skill</h2>
      <!-- skill_id 输入 -->
      <!-- local_ref 路径 OR zip 文件上传（两选一） -->
      <!-- [开始] 按钮 → POST /conversations/start -->
    </div>

    <!-- 对话区（conversation 创建后展示） -->
    <div id="chat-panel" class="hidden flex-1 flex flex-col">
      <!-- conversation_id / auto_run_count x/5 展示 -->
      <!-- 消息气泡区（轮播） -->
      <div id="messages-area" class="flex-1 overflow-y-auto p-4 space-y-3"></div>
      <!-- 状态横幅：409 / 403 frozen / quota 熔断 -->
      <div id="status-banner" class="hidden px-4 py-2 text-sm"></div>
      <!-- 输入区 -->
      <div class="p-4 border-t">
        <textarea id="chat-input" rows="2" placeholder="告诉 Agent 你需要什么帮助..."></textarea>
        <div class="flex gap-2 mt-2">
          <button id="btn-send">发送</button>
          <!-- 【整包确认】按钮：仅当 gap_zero && case_gate_passed && !auto_confirmed 时显示 -->
          <button id="btn-confirm-all" class="hidden bg-green-600 text-white">
            ✅ 整包确认（触发全量评估）
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 右栏：Report 卡片 (60%) -->
  <div class="w-3/5 space-y-4 overflow-y-auto">
    <!-- Evaluating 骨架屏（run running 时显示） -->
    <div id="eval-skeleton" class="hidden ..."></div>
    <!-- skill_summary 卡片 -->
    <div id="card-summary" class="hidden bg-white rounded-xl border p-6">...</div>
    <!-- gaps 卡片 -->
    <div id="card-gaps" class="hidden ...">...</div>
    <!-- 分数 / case 覆盖率 / 风险溯源 / security 徽标 -->
    <div id="card-score" class="hidden ...">...</div>
    <!-- staging case 预览（LUI 写入的 case 展示） -->
    <div id="card-cases" class="hidden ...">...</div>
  </div>

</div>
```

### 5.2 UI 轮询逻辑（伪码）

```javascript
let pollInterval = null;

function startPolling(convId) {
  pollInterval = setInterval(async () => {
    const status = await fetch(`/conversations/${convId}/status`).then(r => r.json());
    updateStatusBanner(status);
    updateAutoRunBadge(status.auto_run_count, status.max_auto_runs);
    updateConfirmAllButton(status.gap_zero, status.case_gate_passed, status.auto_confirmed);

    // run 完成 → 拉 messages
    if (!RUNNING_STATUSES.has(status.run_status)) {
      const msgs = await fetch(`/conversations/${convId}/messages`).then(r => r.json());
      renderMessages(msgs.messages);

      // 首次完成且无 Agent 消息 → 触发开场白
      if (msgs.messages.filter(m => m.role === 'agent').length === 0
          && status.run_status === 'completed') {
        await triggerAgentOpening(convId);
      }

      // 拉 report
      const report = await fetch(`/eval/report/${status.active_run_id}`).then(r => r.json());
      renderReportCards(report);
    } else {
      showEvalSkeleton();
    }
  }, 3000);
}

async function triggerAgentOpening(convId) {
  await fetch(`/conversations/${convId}/chat`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ message: '__TRIGGER_AGENT_OPENING__' })
  });
}

async function sendConfirmAll(convId) {
  await fetch(`/conversations/${convId}/chat`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ message: '__SYSTEM_ACTION_CONFIRM_ALL__' })
  });
}
```

### 5.3 Debug 模式开关

```html
<!-- Header 右上角 -->
<button id="debug-toggle" onclick="toggleDebug()" class="text-xs text-gray-400">
  🔧 Debug
</button>
<!-- Debug 面板（默认 hidden） -->
<div id="debug-panel" class="hidden bg-yellow-50 border border-yellow-200 p-4">
  <!-- 原有「手填路径 + POST /eval/run」UI -->
</div>
```

---

## 6. 新文件与修改文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `skillhub_eval/core/lui_agent.py` | **新建** | LUI Agent |
| `skillhub_eval/core/staging_writer.py` | **新建** | Staging Writer |
| `skillhub_eval/adapters/api/routes/chat.py` | **新建** | /chat, /messages, /status, /confirm-cases |
| `skillhub_eval/adapters/api/_session.py` | **新建** | Session Gate 共用函数 |
| `skillhub_eval/core/schemas/enums.py` | **修改** | 新增 `RUNNING_STATUSES` |
| `skillhub_eval/core/ports.py` | **修改** | 新增 5 个 Port 方法 |
| `skillhub_eval/persistence/sqlite.py` | **修改** | 实现 5 个新方法；DB version 2 migration |
| `skillhub_eval/adapters/api/routes/conversations.py` | **修改** | 支持 multipart zip 上传 |
| `skillhub_eval/adapters/api/routes/eval.py` | **修改** | submit_review conversation 联动 |
| `skillhub_eval/adapters/api/app.py` | **修改** | 注册 chat router |
| `skillhub_eval/adapters/ui/static/index.html` | **修改** | UI 双栏对话重构 |
| `tests/core/test_lui_agent.py` | **新建** | LUI Agent 单元测试 |
| `tests/core/test_staging_writer.py` | **新建** | Staging Writer 单元测试 |
| `tests/api/test_chat.py` | **新建** | API 集成测试 |
| `tests/persistence/test_wave4_infra.py` | **新建** | DB migration + 新 Port 方法测试 |

---

## 7. 端到端流程图（Demo 剧本 A）

```
用户 → POST /conversations/start (local_ref: grill-me)
      → conversation_id + run_id (R_101 degraded, BackgroundTask)

UI 轮询 GET /status (每 3s)
      → run_status: completed + messages_count: 0
      → 前端发 POST /chat {__TRIGGER_AGENT_OPENING__}
      → lui_agent.generate_opening() → lui_messages(agent: "我扫描了...")
      → UI 渲染开场白 + 右侧 report 卡片

用户输入: "帮我补 edge case"
      → POST /chat {message: "帮我补 edge case"}
      → check_session_gate (pass)
      → lui_agent.respond() → intent=mutation, patch={eval_cases:[{type:edge,...}]}
      → staging_writer.apply_patch() → eval_cases/lui_ec_00.yaml 写入
      → staging_writer.trigger_next_run() → R_102 (degraded → check_case_gate)
      → new_run_id 返回前端
      → UI 显示 "Evaluating..." 骨架屏

UI 轮询 → R_102 completed → 更新 report 卡片
status.gap_zero=True + case_gate_passed=True → 显示【整包确认】按钮

用户点击【整包确认】
      → POST /chat {__SYSTEM_ACTION_CONFIRM_ALL__}
      → (绕过 LLM) set_auto_confirmed(True)
      → staging_writer.trigger_next_run() → R_103 capability_full + confirmed
      → engine 运行双模型完整评审
      → report: review_status=pass/warn/fail
```
