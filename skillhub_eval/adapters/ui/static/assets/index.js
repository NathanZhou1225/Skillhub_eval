// ── Config ────────────────────────────────────────────────────────────────────
const API = '';   // same origin; set to 'http://localhost:8000' if needed
let _pollTimer = null;
let _currentRunId = null;
let _confirmSkillId = null;
let _lastGapsSnapshot = null;
let _conversationPollTimer = null;
let _lastConversationPollAt = null;
let _conversationPollFailCount = 0;
let _conversationPollInFlight = false;
let _lastFetchedMessageCount = null;
let _lastFetchedMessagesRunId = null;
let _lastFetchedMessagesRunStatus = null;
let _sessionListInFlight = false;
let _lastSessionListRefreshAt = 0;
let _activeConversationId = null;
const _stagingPathByConversation = Object.create(null);

function getCachedStagingPath(conversationId = _activeConversationId) {
  if (!conversationId) return '';
  return String(_stagingPathByConversation[conversationId] || '').trim();
}

function rememberStagingPath(conversationId, stagingPath) {
  const path = String(stagingPath || '').trim();
  if (!conversationId || !path) return;
  _stagingPathByConversation[conversationId] = path;
}
let _activeRunId = null;
let _latestConversationStatus = null;
let _messagesCache = [];
let _lastRenderedMessageKeys = [];
let _openingTriggeredRunId = null;
const CONV_STORAGE_KEY = 'skillhub_active_conversation_id';
const PERSPECTIVE_KEY = 'skillhub_perspective';
const DEMO_MODE_KEY = 'skillhub_demo_local_ref';
let _pendingZipFile = null;
let _optimisticPending = false;
let _optimisticPendingLabel = '';
let _execScanCache = { scanned_at: null, agents: [] };
let _execScanLoading = false;
let _execScanSeq = 0;
let _execPreferences = null;
let _execPollTimer = null;
let _execBannerDismissed = false;
const _execAgentTestStatus = {};
const _runtimePreflightStatus = {};
let _bridgePromptEl = null;
let _pendingFormalResume = false;
let _pendingFormalAction = null;
let _execConflictContext = null;
let _skipFormalConflictOnce = false;
let _historyFilterKey = 'all';

const ACTION_PROPAGATE = '__ACTION_PROPAGATE__';
const ACTION_MANUAL_UPLOAD = '__ACTION_MANUAL_UPLOAD__';
const ACTION_DRAFT_MODE = '__ACTION_DRAFT_MODE__';
const ACTION_DRAFT_CONFIRM = '__ACTION_DRAFT_CONFIRM__';
const ACTION_CONFIRM_SKILL = '__ACTION_CONFIRM_SKILL__';
const ACTION_DRAFT_WRITE_FILE = '__ACTION_DRAFT_WRITE_FILE__';
const ACTION_SCENE_PROPAGATE = '__ACTION_SCENE_PROPAGATE__';
const ACTION_START_FORMAL = '__ACTION_START_FORMAL__';
const ACTION_READINESS_DRAFT = '__ACTION_READINESS_DRAFT__';

const SECURITY_STATUS_ZH = { passed: '通过', warning: '警告', blocked: '已拦截', unknown: '未知' };
const RISK_LEVEL_ZH = { low: '低', medium: '中', high: '高' };

function isInternalUserMessage(text) {
  const t = String(text || '').trim();
  return t.startsWith('__ACTION_') || t.startsWith('__SYSTEM_') || t.startsWith('__TRIGGER_');
}

function pendingPhaseForCurrentStatus() {
  // D4: chip-click and typed confirmation/correction both land on the same
  // backend branch (skill-id confirm), so key the optimistic label off the
  // conversation's current status rather than how the message was sent.
  const convStatus = getStatusValue(_latestConversationStatus || {}, ['status', 'conversation_status'], '');
  if (convStatus === 'awaiting_skill_id_confirm') return 'checking_requirements';
  return 'thinking';
}

function activityPhaseForAction(payloadText) {
  const t = String(payloadText || '').trim();
  if (t === ACTION_CONFIRM_SKILL) return 'checking_requirements';
  if (t === ACTION_PROPAGATE) return 'propagating';
  if (t === ACTION_DRAFT_WRITE_FILE) return 'writing_draft';
  return 'thinking';
}

function isFormalActionMessage(payloadText) {
  const t = String(payloadText || '').trim();
  return t === ACTION_START_FORMAL || t === '__SYSTEM_ACTION_CONFIRM_ALL__';
}

function getExecSource() {
  return _execPreferences?.exec_source || 'sample_io';
}

function shouldBlockFormalEval() {
  return getExecSource() === 'local' && !_execPreferences?.ready;
}

/** stage_progress may contain stage strings or stage_budget event objects. */
function normalizeStageToken(stage) {
  if (!stage) return '';
  if (typeof stage === 'string') return stage;
  if (typeof stage === 'object') {
    if (stage.stage) return String(stage.stage);
    if (stage.event === 'stage_budget' && stage.stage) return String(stage.stage);
  }
  return '';
}

function latestStageToken(stages, fallback = '') {
  if (Array.isArray(stages)) {
    for (let i = stages.length - 1; i >= 0; i--) {
      const token = normalizeStageToken(stages[i]);
      if (token) return token;
    }
  }
  return normalizeStageToken(fallback) || String(fallback || '');
}

function stageLabelForExec(stage, execSource) {
  const source = execSource || getExecSource();
  const s = normalizeStageToken(stage);
  if (s === 'case_executing') {
    if (source === 'local') return '本地 Agent 真跑中 <span class="badge bg-blue-100 text-blue-700 border-blue-200">[LOCAL]</span>';
    return '校验样例输出';
  }
  if (s === 'local_execution_check') return '本地执行环境检查';
  return STAGE_ZH[s] || s || '评估';
}

function evalProgressLabel(stage, execSource) {
  const source = execSource || getExecSource();
  const agent = _execPreferences?.exec_agent || 'local';
  const agentLabel = EXEC_AGENT_LABELS[agent] || agent;
  const s = normalizeStageToken(stage);
  if (source === 'local') {
    if (s === 'local_execution_check') {
      return '正在检查本地执行环境（准备轻量检查用例并验证 CLI 能读取当前 Skill），请稍候…';
    }
    if (s === 'case_executing') {
      return `正在通过本地 Agent 执行评测案例（${agentLabel}），每个案例约需 30–60 秒，请稍候…`;
    }
    if (s === 'code_asserting') return '正在校验本地 Agent 输出…';
    if (s === 'model_judging') return '本地 Agent 执行已完成，正在进行双模型质量评审…';
    if (s === 'aggregating') return '正在汇总评估结果…';
    if (s === 'risk_locking' || s === 'normalizing') {
      return '正在准备正式评估（锁定风险与整理条件）…';
    }
    if (s === 'level0_checking' || s === 'pending') return '正在启动正式评估…';
    return '正式评估进行中（本地 Agent 模式）…';
  }
  if (s === 'model_judging') return '样例校验完成，正在进行双模型质量评审…';
  if (s === 'case_executing') return '正在读取样例输出并执行规则校验…';
  return '正在进行正式评估，请稍候…';
}

function getLatestAssessmentGatePayload(messages = _messagesCache) {
  if (!Array.isArray(messages)) return null;
  for (let i = messages.length - 1; i >= 0; i--) {
    const mt = messages[i]?.message_type || 'text';
    if (mt !== 'assessment_gate_result') continue;
    return messages[i]?.payload_json || null;
  }
  return null;
}

function clearBridgePromptCard() {
  if (_bridgePromptEl?.parentElement) {
    _bridgePromptEl.parentElement.removeChild(_bridgePromptEl);
  }
  _bridgePromptEl = null;
}

function renderBridgePromptCard() {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const shouldShow = !!_pendingFormalAction;
  if (!shouldShow) {
    clearBridgePromptCard();
    return;
  }
  if (_bridgePromptEl && _bridgePromptEl.parentElement !== container) {
    _bridgePromptEl = null;
  }
  if (!_bridgePromptEl) {
    _bridgePromptEl = document.createElement('div');
    _bridgePromptEl.className = 'flex justify-start';
  }
  const ready = !!_execPreferences?.ready;
  const borderCls = ready
    ? 'border-green-300 border-l-4 border-l-green-600 bg-green-50/80'
    : 'border-amber-300 border-l-4 border-l-amber-600 bg-amber-50/80';
  const title = ready ? '本地执行环境已就绪' : '本地执行暂未就绪';
  const body = ready
    ? '检测到本地执行已可用，正在自动续跑正式评估…'
    : `正式评估已暂停：${escapeHtml(getExecReadyReason())}`;
  const steps = ready ? '' : `
    <ol class="list-decimal list-inside text-xs text-amber-900/90 mt-1 space-y-0.5">
      <li>打开右上角「执行设置」并选择可用 Agent</li>
      <li>确认 Agent 已登录，必要时点击 Test</li>
      <li>勾选本地执行同意项</li>
    </ol>
    <p class="mt-2 text-xs text-amber-800">正在监听…</p>`;
  _bridgePromptEl.innerHTML = `
    <div class="max-w-[95%] w-full rounded-2xl border ${borderCls} p-3 text-sm">
      <div class="text-sm font-semibold ${ready ? 'text-green-900' : 'text-amber-900'}">${title}</div>
      <p class="mt-1 text-xs ${ready ? 'text-green-800' : 'text-amber-800'}">${body}</p>
      ${steps}
    </div>`;
  container.appendChild(_bridgePromptEl);
}

function showBridgePromptCard(actionToken) {
  _pendingFormalAction = actionToken || ACTION_START_FORMAL;
  _pendingFormalResume = true;
  renderMessages(_messagesCache);
}

async function resumePendingFormalEval() {
  if (!_pendingFormalAction) return;
  if (shouldBlockFormalEval()) {
    renderBridgePromptCard();
    return;
  }
  const action = _pendingFormalAction;
  _pendingFormalAction = null;
  _pendingFormalResume = false;
  renderMessages(_messagesCache);
  await sendConversationMessage(action, true);
}

function shouldShowExecConflictModal(bundleExecutionSource) {
  return bundleExecutionSource === 'local' && getExecSource() === 'sample_io';
}

function showExecConflictModal(actionToken) {
  _execConflictContext = { actionToken: actionToken || ACTION_START_FORMAL };
  document.getElementById('exec-conflict-modal')?.classList.remove('hidden');
}

function hideExecConflictModal() {
  document.getElementById('exec-conflict-modal')?.classList.add('hidden');
}

function continuePendingFormalAfterConflict() {
  const action = _execConflictContext?.actionToken || ACTION_START_FORMAL;
  _execConflictContext = null;
  if (shouldBlockFormalEval()) {
    showBridgePromptCard(action);
    return;
  }
  sendConversationMessage(action, true);
}

function proceedFormalWithSample() {
  _skipFormalConflictOnce = true;
  hideExecConflictModal();
  continuePendingFormalAfterConflict();
}

async function switchToLocalAndProceed() {
  try {
    await putExecPreferences({ exec_source: 'local' });
    hideExecConflictModal();
    openExecSettingsDrawer();
    continuePendingFormalAfterConflict();
  } catch (e) {
    toast(`切换失败：${e.message}`, false);
  }
}

function formatSecurityZh(payload, field) {
  if (field === 'security') {
    return payload.security_status_zh || SECURITY_STATUS_ZH[payload.security_status] || payload.security_status || '—';
  }
  return payload.risk_level_locked_zh || RISK_LEVEL_ZH[payload.risk_level_locked] || payload.risk_level_locked || '—';
}

function isSecurityBlocked(payload) {
  return payload && payload.security_status === 'blocked';
}

function securityStatusColorClass(payload) {
  const security = formatSecurityZh(payload, 'security');
  if (security === '通过') return 'text-green-700 font-semibold';
  if (isSecurityBlocked(payload) || security === '已拦截') return 'text-red-700 font-semibold';
  if (security === '警告') return 'text-amber-700 font-semibold';
  return 'text-slate-800 font-semibold';
}

function renderSecurityFindingsHtml(payload) {
  const intake = Array.isArray(payload.security_findings) ? payload.security_findings : [];
  const cases = Array.isArray(payload.security_case_findings) ? payload.security_case_findings : [];
  if (!intake.length && !cases.length) return '';

  const renderRow = (f, blocked) => {
    const label = f.finding_type_zh || f.finding_type || '安全规则';
    const source = f.source === 'skill_bundle' ? 'Skill 正文/脚本' : (f.source || '—');
    const hint = f.hint_zh || '';
    const note = f.note_zh ? `<p class="text-slate-500 mt-0.5">${escapeHtml(f.note_zh)}</p>` : '';
    const match = f.matched_text
      ? `<p class="text-slate-500 mt-0.5 font-mono text-[10px] break-all">${escapeHtml(f.matched_text)}</p>`
      : '';
    const border = blocked ? 'border-red-200 bg-red-50/80' : 'border-slate-200 bg-slate-50/80';
    return `
      <li class="px-2 py-1.5 rounded border ${border}">
        <div class="font-medium ${blocked ? 'text-red-900' : 'text-slate-800'}">${escapeHtml(label)} <span class="text-slate-500 font-normal">· ${escapeHtml(source)}</span></div>
        ${hint ? `<p class="text-xs mt-0.5 ${blocked ? 'text-red-800' : 'text-slate-600'}">${escapeHtml(hint)}</p>` : ''}
        ${note}
        ${match}
      </li>`;
  };

  let html = '';
  if (isSecurityBlocked(payload)) {
    const reason = payload.security_block_reason_zh
      || '安全门禁未通过，无法自动开始正式评估。请修改 Skill 正文或脚本后重试。';
    html += `
      <div class="mt-2 px-3 py-2.5 border-2 border-red-300 rounded-lg bg-red-50 text-xs text-red-900 leading-relaxed">
        <div class="font-bold text-red-800 mb-1">安全门禁未通过 — 无法开始正式评估</div>
        <p>${escapeHtml(reason)}</p>
      </div>`;
  }
  if (intake.length) {
    html += `
      <div class="mt-2">
        <div class="text-xs font-medium text-red-900 mb-1">须修改（Skill 包）</div>
        <ul class="space-y-1.5 text-xs">${intake.map((f) => renderRow(f, true)).join('')}</ul>
      </div>`;
  }
  if (cases.length) {
    html += `
      <div class="mt-2">
        <div class="text-xs font-medium text-slate-700 mb-1">评测题扫描参考（不阻断开评）</div>
        <ul class="space-y-1.5 text-xs">${cases.map((f) => renderRow(f, false)).join('')}</ul>
      </div>`;
  }
  return html;
}

const STAGE_ZH = {
  pending: '排队中',
  level0_checking: '检查包结构',
  risk_locking: '锁定风险等级',
  normalizing: '整理评估条件',
  local_execution_check: '本地执行环境检查',
  case_executing: '执行评测案例',
  code_asserting: '校验输出',
  model_judging: '双模型评估中',
  aggregating: '汇总结果',
};

const STAGE_ORDER = [
  'pending',
  'level0_checking',
  'risk_locking',
  'normalizing',
  'local_execution_check',
  'case_executing',
  'code_asserting',
  'model_judging',
  'divergence_synthesis',
  'aggregating',
];

function stageRank(stage) {
  const idx = STAGE_ORDER.indexOf(normalizeStageToken(stage));
  return idx >= 0 ? idx : -1;
}

function currentRunStageToken(statusObj) {
  const status = statusObj || {};
  const stages = getStatusValue(status, ['stage_progress'], []);
  const fromProgress = latestStageToken(stages, '');
  const runStatus = normalizeStageToken(getStatusValue(status, ['run_status', 'active_run_status', 'status'], ''));
  if (!runStatus) return fromProgress;
  if (!fromProgress) return runStatus;
  return stageRank(runStatus) >= stageRank(fromProgress) ? runStatus : fromProgress;
}

function activityPhaseLabel(phase, statusObj) {
  if (phase === 'formal_eval') {
    return evalProgressLabel(currentRunStageToken(statusObj || _latestConversationStatus || {}), getExecSource());
  }
  const map = {
    thinking: '正在理解你的意思，请稍候…',
    enriching_plan: '正在分析 Skill、检查评估条件并生成材料补充计划，请稍候…',
    checking_requirements: '正在分析 Skill、检查评估条件并生成材料补充计划，请稍候…',
    propagating: '正在自动生成评估题目，请稍候（约 1–2 分钟）…',
    initial_eval: '正在进行初评体检，请稍候（约 1–3 分钟）…',
    formal_eval: evalProgressLabel(null, getExecSource()),
    writing_draft: '正在生成修改草案，请稍候…',
  };
  return map[phase] || map.thinking;
}

const KEEP_PENDING_PHASES = new Set([
  'checking_requirements', 'enriching_plan', 'propagating', 'initial_eval', 'formal_eval', 'writing_draft',
]);

function syncPendingFromRunStatus(statusObj) {
  const runStatus = getStatusValue(statusObj, ['run_status', 'active_run_status', 'status'], '');
  const runStartedAt = getStatusValue(statusObj, ['run_started_at', 'active_run_started_at'], '');
  if (isRunActivelyExecuting(runStatus, runStartedAt)) {
    _optimisticPending = true;
    _optimisticPendingLabel = evalProgressLabel(currentRunStageToken(statusObj), getExecSource());
    return;
  }
  if (!_optimisticPending) {
    _optimisticPendingLabel = '';
  }
}

function renderFlowStepBar(flowStep) {
  if (!flowStep || !flowStep.label_zh) return '';
  const cur = flowStep.current || 1;
  const total = flowStep.total || 3;
  return `
    <div class="mb-2 px-2 py-1.5 rounded-lg bg-amber-100/80 border border-amber-200 text-xs text-amber-900">
      第 ${cur}/${total} 步 · ${escapeHtml(flowStep.label_zh)}
    </div>`;
}

function formatRedlineCell(row) {
  const isRedline = row.redline === true || row.redline === 'true'
    || row.type === 'refusal' || row.type === 'adversarial';
  if (!isRedline) return '非红线题型';
  const note = (row.redline_note || '').trim();
  if (note) return `红线题型（一票否决） · ${note}`;
  return '红线题型（一票否决） · 须明确拒绝边界与越权防护';
}

function isRedlineRow(row) {
  return row.redline === true || row.redline === 'true'
    || row.type === 'refusal' || row.type === 'adversarial';
}

function renderRedlineNote(row) {
  if (!isRedlineRow(row)) return '';
  const note = (row.redline_note || '').trim() || '须明确拒绝边界与越权防护';
  const uid = 'rl' + Math.random().toString(36).slice(2, 7);
  return `<details class="mt-1">
    <summary class="cursor-pointer text-red-600 text-xs font-medium inline-flex items-center gap-1">
      <span class="inline-block w-1.5 h-1.5 keep-round bg-red-500"></span>红线 ▾
    </summary>
    <p class="text-xs text-red-700 mt-1 pl-3 border-l-2 border-red-200 leading-relaxed">${escapeHtml(note)}</p>
  </details>`;
}

function statusLabel(s) {
  return {
    pass: '通过',
    warn: '待改进',
    fail: '未通过',
    completed: '已完成',
    failed: '失败',
    awaiting_human_review: '待审核',
    awaiting_confirm: '待补全',
  }[s] || s || '—';
}

function formatGapCell(row) {
  const n = row.gap_count ?? row.gap;
  return n != null && n !== '' ? String(n) : '—';
}

function getPerspective() {
  try { return localStorage.getItem(PERSPECTIVE_KEY) || 'author'; } catch (_) { return 'author'; }
}

function setPerspective(p) {
  try { localStorage.setItem(PERSPECTIVE_KEY, p); } catch (_) {}
  const authorBtn = document.getElementById('btn-perspective-author');
  const expertBtn = document.getElementById('btn-perspective-expert');
  if (authorBtn && expertBtn) {
    authorBtn.className = p === 'author'
      ? 'px-3 py-1.5 bg-blue-600 text-white font-medium'
      : 'px-3 py-1.5 bg-white text-gray-600';
    expertBtn.className = p === 'expert'
      ? 'px-3 py-1.5 bg-blue-600 text-white font-medium relative'
      : 'px-3 py-1.5 bg-white text-gray-600 relative';
  }
  _lastRenderedMessageKeys = [];
  renderMessages(_messagesCache);
  updateComposerState();
  if (_latestConversationStatus) updateChatStatusBanner(_latestConversationStatus);
  loadSessionList({ force: true });
}

function toggleDemoMode() {
  const on = localStorage.getItem(DEMO_MODE_KEY) !== 'true';
  try { localStorage.setItem(DEMO_MODE_KEY, on ? 'true' : 'false'); } catch (_) {}
  document.getElementById('demo-path-wrap').classList.toggle('hidden', !on);
  toast(on ? 'Demo 模式已开启（可填本地路径）' : 'Demo 模式已关闭');
}

function onZipSelected() {
  const input = document.getElementById('chat-zip-file');
  _pendingZipFile = input.files?.[0] || null;
  document.getElementById('chat-zip-name').textContent = _pendingZipFile ? _pendingZipFile.name : '';
}

async function createNewSession() {
  try {
    const data = await apiFetch('/conversations/new', { method: 'POST' });
    await selectSession(data.conversation_id);
    await loadSessionList({ force: true });
    toast('新对话已创建');
  } catch (e) {
    toast(e.message, false);
  }
}

const RUNNING_STATUSES = new Set([
  'pending', 'level0_checking', 'risk_locking', 'normalizing',
  'case_executing', 'code_asserting', 'model_judging', 'aggregating'
]);

// Keep in sync with skillhub_eval/core/latency.py run_lock_timeout_seconds()
const RUN_LOCK_TIMEOUT_S = 5400 + 900;

function isRunActivelyExecuting(runStatus, startedAtIso) {
  if (!RUNNING_STATUSES.has(String(runStatus))) return false;
  if (!startedAtIso) return true;
  const startedMs = Date.parse(startedAtIso);
  if (Number.isNaN(startedMs)) return true;
  return (Date.now() - startedMs) / 1000 < RUN_LOCK_TIMEOUT_S;
}

let _sessionListCache = [];

function archiveBlockReason(conv, perspective) {
  if (!conv) return null;
  const runStatus = conv.active_run_status || '';
  if (isRunActivelyExecuting(runStatus, conv.active_run_started_at)) {
    return '评估进行中，请稍后再删除';
  }
  if (perspective === 'expert') return null;
  if (conv.status === 'frozen') {
    return '会话已冻结，请切换到右上角【专家】视角后再删除';
  }
  if (conv.human_review_pending) {
    return '该会话待专家复核，请切换到【专家】视角后再删除';
  }
  return null;
}

async function loadSessionList(opts = {}) {
  const force = opts.force === true;
  const now = Date.now();
  if (!force && now - _lastSessionListRefreshAt < 15000) return;
  if (_sessionListInFlight) return;
  _sessionListInFlight = true;
  const el = document.getElementById('session-list');
  try {
    const data = await apiFetch('/conversations?limit=50');
    _lastSessionListRefreshAt = Date.now();
    const convs = data.conversations || [];
    _sessionListCache = convs;
    const perspective = getPerspective();
    if (!convs.length) {
      el.innerHTML = '<p class="text-xs text-gray-400 text-center py-4">暂无会话</p>';
      return;
    }
    el.innerHTML = convs.map((c, i) => {
      const active = c.conversation_id === _activeConversationId;
      const pending = c.human_review_pending;
      const label = c.skill_id || c.last_message_preview?.slice(0, 20) || c.conversation_id.slice(0, 8);
      const refNo = `№${String(convs.length - i).padStart(3, '0')}`;
      const cid = escapeHtml(c.conversation_id);
      const blockReason = archiveBlockReason(c, perspective);
      const deleteTitle = escapeHtml(blockReason || '从侧栏移除');
      const deleteBtnClass = blockReason
        ? 'absolute right-1 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-amber-600 hover:text-amber-700 hover:bg-amber-50 text-xs opacity-70 group-hover:opacity-100 focus:opacity-100'
        : 'absolute right-1 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-gray-400 hover:text-red-600 hover:bg-red-50 text-xs opacity-0 group-hover:opacity-100 focus:opacity-100';
      return `<div class="group relative flex items-stretch border-l-2 ${active ? 'bg-blue-50 border-l-blue-600' : 'border-l-transparent hover:bg-gray-50'}">
        <button type="button" onclick="selectSession('${cid}')"
          class="flex-1 min-w-0 text-left px-2 py-2 text-xs ${active ? 'text-blue-800' : 'text-gray-700'}">
          <div class="flex items-center gap-1.5 min-w-0 pr-6">
            <span class="run-ref text-[10px] ${active ? 'text-blue-600' : 'text-gray-400'} shrink-0">${refNo}</span>
            <span class="font-medium truncate">${escapeHtml(label)}</span>
          </div>
          <div class="text-gray-400 truncate">${escapeHtml((c.last_message_preview || '').slice(0, 40))}${pending ? ' · 待审' : ''}${blockReason ? ' · 需专家删除' : ''}</div>
        </button>
        <button type="button" title="${deleteTitle}" onclick="archiveSession('${cid}', event, ${i})"
          class="${deleteBtnClass}">×</button>
      </div>`;
    }).join('');
    const anyPending = convs.some(c => c.human_review_pending);
    document.getElementById('expert-pending-dot')?.classList.toggle('hidden', !anyPending);
  } catch (e) {
    el.innerHTML = `<p class="text-xs text-red-400 py-4">${escapeHtml(e.message)}</p>`;
  } finally {
    _sessionListInFlight = false;
  }
}

async function selectSession(convId) {
  _activeConversationId = convId;
  _activeRunId = null;
  _latestConversationStatus = null;
  _lastFetchedMessageCount = null;
  _lastFetchedMessagesRunId = null;
  _lastFetchedMessagesRunStatus = null;
  _lastRenderedMessageKeys = [];
  persistConversationId(convId);
  document.getElementById('chat-conversation-id').textContent = convId;
  updateChatLocalCheckButton();
  renderExecAgentCards();
  startConversationPolling();
  await pollConversation({ force: true, forceMessages: true });
  await loadSessionList({ force: true });
}

async function archiveSession(convId, ev, listIndex) {
  if (ev) ev.stopPropagation();
  const perspective = getPerspective();
  const conv = typeof listIndex === 'number'
    ? _sessionListCache[listIndex]
    : _sessionListCache.find(c => c.conversation_id === convId);
  const block = archiveBlockReason(conv, perspective);
  if (block) {
    toast(block, false);
    return;
  }
  const ok = confirm(
    '从侧栏移除此对话？\n\n评估记录与对话内容仍可在【评估历史】中查看，不会被删除。'
  );
  if (!ok) return;
  const wasActive = convId === _activeConversationId;
  try {
    await apiFetch(
      `/conversations/${encodeURIComponent(convId)}?perspective=${encodeURIComponent(perspective)}`,
      { method: 'DELETE' },
    );
    if (wasActive) {
      resetConversationView();
      clearStoredConversationId();
      _messagesCache = [];
      _lastRenderedMessageKeys = [];
      renderMessages([]);
      document.getElementById('chat-messages').innerHTML =
        '<p class="text-sm text-gray-400 text-center py-16">未选择会话</p>';
    }
    await loadSessionList({ force: true });
    if (wasActive) {
      const data = await apiFetch('/conversations?limit=50');
      const convs = data.conversations || [];
      if (convs.length) {
        await selectSession(convs[0].conversation_id);
      }
    }
    toast('已从侧栏移除');
  } catch (e) {
    if (e.status === 403) {
      toast(e.message || '当前状态不可删除', false);
    } else if (e.status === 409) {
      toast(e.message || '评估进行中，请稍后再试', false);
    } else if (e.status === 404) {
      const msg = (e.message === 'Not Found')
        ? '删除接口不可用，请重启评估服务后重试'
        : (e.message || '会话不存在或已被移除');
      toast(msg, false);
    } else {
      toast(e.message || '删除失败', false);
    }
  }
}

function persistConversationId(convId) {
  if (convId) {
    try { localStorage.setItem(CONV_STORAGE_KEY, convId); } catch (_) {}
  }
}

function readStoredConversationId() {
  try { return localStorage.getItem(CONV_STORAGE_KEY) || null; } catch (_) { return null; }
}

function clearStoredConversationId() {
  try { localStorage.removeItem(CONV_STORAGE_KEY); } catch (_) {}
}

async function resumeConversation(convId, runIdHint) {
  if (!convId) return false;
  try {
    const statusObj = await apiFetch(`/conversations/${encodeURIComponent(convId)}/status`);
    _activeConversationId = convId;
    _activeRunId = runIdHint || statusObj.active_run_id || null;
    persistConversationId(convId);
    document.getElementById('chat-conversation-id').textContent = convId.slice(0, 12) + '…';
    const maxRuns = statusObj.max_auto_runs || 5;
    const autoRuns = statusObj.auto_run_count || 0;
    document.getElementById('chat-run-badge').textContent = `${autoRuns}/${maxRuns}`;
    updateChatLocalCheckButton();
    renderExecAgentCards();
    switchTab('author');
    startConversationPolling();
    await pollConversation({ force: true, forceMessages: true });
    toast('已恢复会话');
    return true;
  } catch (e) {
    if (e.status === 404) clearStoredConversationId();
    toast('无法恢复会话：' + (e.message || '未知错误'), false);
    return false;
  }
}

async function resumeStoredConversation() {
  const convId = readStoredConversationId();
  if (!convId) {
    toast('没有可恢复的会话', false);
    return;
  }
  await resumeConversation(convId);
}

async function offerResumeBanner() { /* legacy no-op — session list handles resume */ }

const SECURITY_FIELDS = ['negative_prompts', 'error_handling', 'permission_scope', 'security_notes'];
const SECURITY_LABELS = {
  negative_prompts: '禁止指令（negative_prompts）',
  error_handling: '错误处理策略（error_handling）',
  permission_scope: '权限范围（permission_scope）',
  security_notes: '安全备注（security_notes）',
};
const SECURITY_PLACEHOLDERS = {
  negative_prompts: '不允许操作的场景或指令',
  error_handling: '遇到异常时的返回格式',
  permission_scope: '允许访问的数据范围',
  security_notes: '其他安全敏感约束',
};

const REASON_ZH = {
  'MODEL_DISAGREEMENT_R5': '双模型评审存在明显分歧，综合分暂不展示',
  'REDLINE_MODEL_DISAGREEMENT': '红线用例上模型判断不一致，需人工复核',
  'WARN_COMPLETENESS_LOW': '元数据完整度未达 90',
  'WARN_SCORE_MIDRANGE': '综合分处于中等档（70–84）',
  'LEVEL0_SCHEMA_FAIL': 'Skill 包结构校验失败',
  'RISK_CASE_COUNT_INSUFFICIENT': '当前风险等级用例数量不足',
  'EVAL_WORKFLOW_TIMEOUT': '评估超时',
  'EVAL_PROVIDER_UNAVAILABLE': '双模型 API 均未返回有效分数',
  'LOCAL_RUNTIME_PREFLIGHT_REQUIRED': '当前 Skill 的本地执行环境检查未通过（旧版阻断结果；新版仅作诊断）',
  'LOCAL_RUNTIME_TOOL_FAILURES_EXCEEDED': '本地 preflight 在多次工具调用失败后已提前终止',
  'LOCAL_RUNTIME_PREFLIGHT_TOOL_BUDGET_EXCEEDED': '本地 preflight 工具调用超出环境检查预算，已提前终止',
  'LOCAL_EXEC_UNAVAILABLE': '本地 Agent 不可用（未检测到或未授权），本次未执行、未出报告',
  'LOCAL_EXEC_ALL_CASES_FAILED': '本地 Agent 执行全部失败，本次未出报告（非静默降级为示例数据）',
  'LOCAL_RUNTIME_CLI_UNAVAILABLE': '本地 CLI 未检测到或不可调用',
  'LOCAL_RUNTIME_AUTH_MISSING': '本地 CLI 未登录或配置不可用',
  'LOCAL_RUNTIME_DEFINITION_MISSING': '该 Agent 缺少 runtime 定义',
  'LOCAL_RUNTIME_PROMPT_TOO_LARGE': '当前 CLI 的命令行 prompt 超过安全长度',
  'LOCAL_RUNTIME_SKILL_INJECTION_UNAVAILABLE': '当前 Skill 无可用注入方式',
  'LOCAL_RUNTIME_RUN_INCOMPLETE': '本地 Runtime 未完成执行或输出流未结束',
  'LOCAL_RUNTIME_PARSER_MISSING': '本地 Runtime 输出无法解析',
  'LOCAL_RUNTIME_MISSING_ENTRYPOINT_EVIDENCE': '未观察到入口脚本执行证据',
  'LOCAL_RUNTIME_OUTPUT_LEAK': '本地产出疑似包含敏感信息，已拦截',
  'LOCAL_RUNTIME_HARDENED_PROFILE_UNAVAILABLE': '该 Runtime 不支持红线题所需强化模式',
  'LOCAL_RUNTIME_SAFE_PREFLIGHT_REQUIRED': '高风险 Skill 缺少安全检查用例（仅诊断，不阻止正式评估）',
  'LOCAL_RUNTIME_ADAPTER_UNAVAILABLE': '该 Runtime 暂无可用 adapter',
};

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  ['author','history'].forEach(t => {
    document.getElementById('panel-'+t).classList.toggle('hidden', t !== name);
    const btn = document.getElementById('tab-'+t);
    if (btn) btn.className = (t === name ? 'tab-active' : 'tab-inactive') + ' py-3 text-sm transition';
  });
  if (name === 'history') loadHistory();
}

// ── API helpers ───────────────────────────────────────────────────────────────
async function apiFetch(path, opts={}) {
  const headers = { ...(opts.headers || {}) };
  const body = opts.body;
  if (!(body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(API + path, { ...opts, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const msg = typeof detail === 'string' ? detail : (detail?.message || res.statusText);
    const ex = new Error(msg);
    ex.status = res.status;
    ex.code = (typeof detail === 'object' && detail?.error) ? detail.error : '';
    throw ex;
  }
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  return JSON.parse(text);
}

const EXEC_AGENT_LABELS = {
  claude: 'Claude Code',
  codex: 'Codex CLI',
  'cursor-agent': 'Cursor Agent',
  trae: 'Trae',
  antigravity: 'Antigravity',
};

function getExecAgentLabel(agentId) {
  if (!agentId) return '未选择 Agent';
  const list = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const match = list.find((a) => a.id === agentId);
  return match?.label || EXEC_AGENT_LABELS[agentId] || agentId;
}

function getSelectedExecAgent() {
  return _execPreferences?.exec_agent || '';
}

function getSelectedExecAgentForAction() {
  return getSelectedExecAgent() || 'cursor-agent';
}

function getSelectedExecModel() {
  return _execPreferences?.exec_model || 'default';
}

function getExecModelLabel(modelId) {
  const value = modelId || 'default';
  if (value === 'default') return '默认模型';
  const models = getExecModelsForSelectedAgent();
  const match = models.find((model) => model.id === value);
  return match?.label || value;
}

function getExecModelsForSelectedAgent() {
  const agentId = getSelectedExecAgent();
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const agent = agents.find((a) => a.id === agentId);
  const models = Array.isArray(agent?.models) ? agent.models : [];
  return models.length ? models : [{ id: 'default', label: '默认模型', source: 'fallback' }];
}

// Shared machine-reason → 中文 map: covers both pre-run readiness gating
// (consent_required/agent_unavailable/...) and post-run per-case degrade
// reasons from ExecResult.degrade_reason (run_incomplete/output_leak/...).
const EXEC_READY_REASON_ZH = {
  consent_required: '请先勾选下方「同意本机执行」',
  agent_unavailable: '所选 Agent 未在本机检测到（请重新扫描或检查 PATH）',
  agent_not_selected: '请先选择一个已检测到的 Agent',
  invalid_exec_source: '执行来源无效',
  run_incomplete: '本地 Agent 未在超时前完成（流式输出未读到结束标记，可能是网络慢、模型繁忙或 CLI 版本不兼容）',
  missing_entrypoint_evidence: '未检测到入口脚本的执行证据（tool_result 缺少 entrypoint 调用记录）',
  output_leak: '产出疑似包含敏感信息，已被安全过滤拦截',
  redline_no_hardened_profile: '当前 Agent 不支持该红线题所需的强化执行模式',
  local_runtime_definition_missing: '该 Agent 缺少 runtime 定义，请先升级 Runtime 配置',
  local_runtime_prompt_too_large: '当前 CLI 通过命令行参数接收 prompt，内容过长，需缩短 case 或改用 stdin/prompt-file runtime',
  local_runtime_skill_injection_unavailable: '当前 skill 无可用注入方式',
  runtime_auth_missing: '本地 CLI 未登录或配置不可用',
  runtime_safe_preflight_required: '本地执行环境检查缺少轻量检查用例',
  runtime_missing_entrypoint_evidence: '环境检查未观察到入口脚本执行证据',
  runtime_run_incomplete: '环境检查未完成或返回错误',
  runtime_parser_missing: '环境检查输出无法解析',
};

const LOCAL_CHECK_STATUS_ZH = {
  missing: '尚未检查',
  passed: '已通过',
  failed: '检查失败',
  expired: '已过期',
  blocked: '诊断未通过（可继续正式评估）',
  not_applicable: '未选择 Skill',
};

function getActiveSkillBundlePath() {
  const fromCache = getCachedStagingPath();
  if (fromCache) return fromCache;
  const inp = document.getElementById('inp-bundle-path');
  const fromInput = inp && inp.value ? inp.value.trim() : '';
  if (fromInput) return fromInput;
  const messages = Array.isArray(_messagesCache) ? _messagesCache : [];
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const payload = messages[i].payload_json || messages[i].payload || {};
    if (payload.skill_bundle_path) return payload.skill_bundle_path;
  }
  return '';
}

function formatLocalCheckStatus(agent) {
  if (!agent || !agent.local_check_status) return '';
  const label = LOCAL_CHECK_STATUS_ZH[agent.local_check_status] || agent.local_check_status;
  const expiry = agent.local_check_expires_at
    ? `（有效至 ${formatScanTime(agent.local_check_expires_at)}）`
    : '';
  return `${label}${expiry}`;
}

function formatClockTime(dateLike) {
  const date = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (!Number.isFinite(date.getTime())) return '';
  return date.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function canRunCurrentLocalExecutionCheck() {
  return getExecSource() === 'local' && !!getActiveSkillBundlePath() && !!getSelectedExecAgent();
}

function formatExecReadyReason(reason) {
  if (!reason) return '';
  return EXEC_READY_REASON_ZH[reason] || reason;
}

function formatRuntimePreflightStatus(item) {
  if (!item) return '';
  const status = item.status === 'passed' ? '通过'
    : item.status === 'failed' ? '失败'
    : item.status === 'blocked' ? '已阻止'
    : item.status || '未知';
  const cached = item.cached ? '（缓存）' : '';
  const reason = item.failure_reason ? `：${formatExecReadyReason(item.failure_reason)}` : '';
  return `${status}${cached}${reason}`;
}

function getExecReadyReason() {
  if (!_execPreferences) return '';
  if (_execPreferences.ready_reason) return formatExecReadyReason(_execPreferences.ready_reason);
  if (_execPreferences.ready) return '本地执行就绪，可直接开始正式评估。';
  return '本地执行未就绪，请检查 Agent 安装、登录状态与同意项。';
}

function formatScanTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (_) {
    return '';
  }
}

function renderExecScanSummary() {
  const el = document.getElementById('exec-scan-summary');
  const btn = document.getElementById('exec-rescan-btn');
  const spinner = document.getElementById('exec-rescan-spinner');
  const label = document.getElementById('exec-rescan-label');
  if (btn) btn.disabled = _execScanLoading;
  spinner?.classList.toggle('hidden', !_execScanLoading);
  if (label) label.textContent = _execScanLoading ? '扫描中…' : '重新扫描';
  if (!el) return;

  if (_execScanLoading) {
    el.className = 'text-xs text-blue-700 leading-relaxed min-h-[1.25rem]';
    el.textContent = '正在扫描本机 CLI Agent（claude / codex / cursor-agent / trae / antigravity）…';
    return;
  }

  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  if (!agents.length) {
    el.className = 'text-xs text-amber-800 leading-relaxed min-h-[1.25rem]';
    el.textContent = '尚未完成扫描，请点击「重新扫描」。';
    return;
  }

  const detected = agents.filter((a) => a.detected);
  const missed = agents.filter((a) => !a.detected);
  const ts = formatScanTime(_execScanCache.scanned_at);
  const parts = [];
  if (detected.length) {
    parts.push(`已检测到 ${detected.length} 个：${detected.map((a) => {
      const path = a.bin_path ? `（${a.bin_path}）` : '';
      return `${a.label || a.id}${path}`;
    }).join('、')}`);
  }
  if (missed.length) {
    parts.push(`未检测到：${missed.map((a) => a.label || a.id).join('、')}`);
  }
  el.className = detected.length
    ? 'text-xs text-green-800 leading-relaxed min-h-[1.25rem]'
    : 'text-xs text-amber-800 leading-relaxed min-h-[1.25rem]';
  el.textContent = `扫描完成${ts ? `（${ts}）` : ''}。${parts.join('；')}`;
}

function renderExecBridgeIndicator() {
  const pill = document.getElementById('exec-bridge-indicator');
  const hint = document.getElementById('exec-sample-hint');
  if (!pill) return;

  const source = _execPreferences?.exec_source || 'sample_io';
  const ready = !!_execPreferences?.ready;
  const agentLabel = getExecAgentLabel(_execPreferences?.exec_agent);
  const modelLabel = getExecModelLabel(getSelectedExecModel());

  if (source === 'local' && ready) {
    pill.textContent = `本地执行：${agentLabel} / ${modelLabel}`;
    pill.className = 'text-xs px-2 py-1 border border-green-300 text-green-800 bg-green-50 hover:bg-green-100 transition';
  } else if (source === 'local') {
    pill.textContent = '本地执行：未就绪';
    pill.className = 'text-xs px-2 py-1 border border-red-300 text-red-800 bg-red-50 hover:bg-red-100 transition';
  } else {
    pill.textContent = '评估模式：样例自证';
    pill.className = 'text-xs px-2 py-1 border border-gray-300 text-gray-600 bg-gray-50 hover:bg-gray-100 transition';
  }

  hint?.classList.toggle('hidden', source !== 'sample_io');
  document.getElementById('exec-sample-disclaimer')?.classList.toggle('hidden', source !== 'sample_io');
}

function renderExecBanner() {
  const el = document.getElementById('exec-ready-banner');
  const text = document.getElementById('exec-ready-banner-text');
  if (!el || !_execPreferences) return;
  const source = _execPreferences.exec_source || 'sample_io';
  const ready = !!_execPreferences.ready;
  const shouldShow = source === 'local' && !ready && !_execBannerDismissed;
  el.classList.toggle('hidden', !shouldShow);
  if (shouldShow && text) {
    text.textContent = `本地执行未就绪：${getExecReadyReason()}`;
  }
}

function dismissExecBanner() {
  _execBannerDismissed = true;
  renderExecBanner();
}

async function switchExecBannerToSample() {
  await putExecPreferences({ exec_source: 'sample_io' });
  _execBannerDismissed = false;
}

function openExecSettingsDrawer() {
  document.getElementById('exec-drawer-overlay')?.classList.remove('hidden');
  renderExecDrawer();
}

function closeExecSettingsDrawer() {
  document.getElementById('exec-drawer-overlay')?.classList.add('hidden');
}

function renderExecAgentModelSelectors() {
  const agentSelect = document.getElementById('exec-agent-select');
  const modelSelect = document.getElementById('exec-model-select');
  if (!agentSelect || !modelSelect) return;

  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const selectedAgent = getSelectedExecAgent();
  if (!agents.length) {
    agentSelect.innerHTML = '<option value="">未扫描</option>';
    modelSelect.innerHTML = '<option value="default">默认模型</option>';
    agentSelect.disabled = true;
    modelSelect.disabled = true;
    return;
  }

  agentSelect.disabled = false;
  modelSelect.disabled = false;
  agentSelect.innerHTML = agents.map((agent) => {
    const disabled = agent.detected ? '' : 'disabled';
    const selected = agent.id === selectedAgent ? 'selected' : '';
    const suffix = agent.detected ? '' : '（未检测到）';
    return `<option value="${escapeHtml(agent.id)}" ${selected} ${disabled}>${escapeHtml(agent.label || agent.id)}${suffix}</option>`;
  }).join('');

  const selectedModel = getSelectedExecModel();
  const models = getExecModelsForSelectedAgent();
  const hasSelected = models.some((model) => model.id === selectedModel);
  const rows = hasSelected
    ? models
    : [{ id: selectedModel, label: `${selectedModel}（自定义）`, source: 'custom' }, ...models];
  modelSelect.innerHTML = rows.map((model) => {
    const selected = model.id === selectedModel ? 'selected' : '';
    const source = model.source && model.source !== 'fallback' ? ` · ${model.source}` : '';
    return `<option value="${escapeHtml(model.id)}" ${selected}>${escapeHtml(model.label || model.id)}${escapeHtml(source)}</option>`;
  }).join('');
}

function copyExecInstallCmd(agentId) {
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const agent = agents.find((a) => a.id === agentId);
  const cmd = agent && agent.install_command ? agent.install_command : '';
  if (!cmd) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(cmd);
  }
}

function renderExecAgentCards() {
  const wrap = document.getElementById('exec-agent-cards');
  if (!wrap) return;
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  if (_execScanLoading && !agents.length) {
    wrap.innerHTML = '<p class="text-xs text-gray-400 flex items-center gap-2"><span class="exec-spin"></span>扫描 Agent 中…</p>';
    return;
  }
  if (!agents.length) {
    wrap.innerHTML = '<p class="text-xs text-gray-400">未扫描到 Agent 列表，请点击「重新扫描」。</p>';
    return;
  }

  const refreshHint = _execScanLoading
    ? '<p class="text-xs text-blue-700 flex items-center gap-2 mb-2"><span class="exec-spin"></span>正在刷新扫描结果…</p>'
    : '';
  const selected = _execPreferences?.exec_agent || '';
  wrap.innerHTML = refreshHint + agents.map((agent) => {
    const detected = !!agent.detected;
    const checked = selected === agent.id;
    const cardClass = checked
      ? 'border border-blue-300 border-l-[3px] border-l-blue-600 bg-blue-50'
      : 'border border-gray-200 border-l-[3px] border-l-transparent bg-white';
    const disabledClass = detected ? '' : ' opacity-60';
    const AUTH_LABELS = { ok: '可用', missing: '未登录', unknown: '待测试' };
    const authState = agent.auth_status || (detected ? 'unknown' : 'missing');
    const authBadgeCls = authState === 'ok' ? 'bg-emerald-100 text-emerald-800'
      : authState === 'missing' ? 'bg-amber-100 text-amber-800'
      : 'bg-gray-200 text-gray-600';
    const auth = detected
      ? `<span class="text-[11px] px-1.5 py-0.5 rounded ${authBadgeCls}">${AUTH_LABELS[authState] || authState}</span>`
      : `<span class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">未安装</span>`;
    const MODEL_SRC_LABELS = { live: '在线获取', fallback: '内置列表', none: '—' };
    const model = (detected && agent.models_source)
      ? `<span class="text-[11px] text-gray-500">模型：${escapeHtml(MODEL_SRC_LABELS[agent.models_source] || agent.models_source)}</span>`
      : '';
    const statusLine = detected
      ? `<div class="text-xs text-green-700 mt-0.5 break-all">已检测到${agent.bin_path ? `：${escapeHtml(agent.bin_path)}` : ''}</div>`
      : `<div class="text-xs text-amber-800 mt-0.5">未检测到（不可选）</div>
         ${agent.detect_hint ? `<div class="text-[11px] text-gray-500 mt-1 leading-relaxed">${escapeHtml(agent.detect_hint)}</div>` : ''}`;
    const installBlock = (!detected && agent.install_command)
      ? `<div class="mt-1 text-[11px] text-gray-500 leading-relaxed">
           <code class="bg-gray-100 px-1 rounded text-gray-700">${escapeHtml(agent.install_command)}</code>
           <button type="button" onclick="event.stopPropagation(); copyExecInstallCmd('${escapeHtml(agent.id)}')" class="ml-2 underline text-blue-600">复制</button>
           ${agent.install_docs_url ? `<a href="${escapeHtml(agent.install_docs_url)}" target="_blank" rel="noopener" class="ml-2 underline text-blue-600">官方文档</a>` : ''}
           ${agent.install_note ? `<div class="text-gray-400 mt-0.5">${escapeHtml(agent.install_note)}</div>` : ''}
           <div class="text-gray-400">装好后点「重新扫描」。</div>
         </div>`
      : '';
    const diagnosisBlock = (detected && agent.diagnosis_ok === false)
      ? `<div class="mt-1 text-[11px] text-red-700 leading-relaxed">
           诊断：${escapeHtml(agent.diagnosis_message || '模型配置检测未通过')}
           ${agent.diagnosis_hint ? `<div class="text-gray-500 mt-0.5">${escapeHtml(agent.diagnosis_hint)}</div>` : ''}
         </div>`
      : '';
    const MODEL_STATUS_CLS = {
      ok: 'text-emerald-700',
      default: 'text-gray-500',
      stale: 'text-amber-700',
      probe_unavailable: 'text-gray-500',
    };
    const modelStatusBlock = (detected && agent.selected_model_status && agent.selected_model_message)
      ? `<div class="mt-0.5 text-[11px] ${MODEL_STATUS_CLS[agent.selected_model_status] || 'text-gray-500'}">已选模型：${escapeHtml(agent.selected_model_message)}</div>`
      : '';
    const testMsg = _execAgentTestStatus[agent.id] || '';
    const testClass = /通过|ok|成功/i.test(testMsg)
      ? 'text-green-700'
      : (/失败|error|未|fail/i.test(testMsg) ? 'text-red-700' : 'text-gray-500');
    const skillPath = getActiveSkillBundlePath();
    const localCheckLine = !skillPath
      ? '<div class="mt-1 text-[11px] text-gray-400">上传 ZIP 后可检查当前 Skill</div>'
      : (agent.local_check_status && agent.local_check_status !== 'not_applicable'
        ? `<div class="mt-1 text-[11px] text-indigo-800 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
             <span class="font-medium">当前 Skill 检查：</span>${escapeHtml(formatLocalCheckStatus(agent))}
             ${agent.local_check_message_zh ? `<span class="text-indigo-600"> — ${escapeHtml(agent.local_check_message_zh)}</span>` : ''}
           </div>`
        : '<div class="mt-1 text-[11px] text-gray-500">当前 Skill 检查：尚未检查（可选诊断）</div>');

    let checkBtn = '';
    if (skillPath && detected) {
      if (agent.can_run_local_check) {
        checkBtn = `<button type="button" class="shrink-0 text-xs px-2 py-1 border border-indigo-300 text-indigo-800 hover:bg-indigo-50"
          onclick="event.stopPropagation(); runLocalExecutionCheck('${escapeHtml(agent.id)}')">
          ${agent.local_check_status === 'passed' ? '重新检查' : '运行环境检查'}
        </button>`;
      } else {
        const blockedHint = escapeHtml(agent.local_check_message_zh || '当前无法自动生成检查用例');
        checkBtn = `<button type="button" disabled title="${blockedHint}"
          class="shrink-0 text-xs px-2 py-1 border border-gray-200 text-gray-400 cursor-not-allowed">
          运行环境检查
        </button>`;
      }
    }
    const switchBtn = (skillPath && agent.can_switch_and_rerun && !checked)
      ? `<button type="button" class="shrink-0 text-xs px-2 py-1 border border-emerald-300 text-emerald-800 hover:bg-emerald-50 ml-1"
          onclick="event.stopPropagation(); switchToVerifiedRuntime('${escapeHtml(agent.id)}')">
          改用此工具
        </button>`
      : '';

    return `
      <label class="block px-3 py-2 cursor-pointer transition ${cardClass}${disabledClass}" onclick="${detected ? `onExecAgentRadioChange('${escapeHtml(agent.id)}')` : ''}">
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-start gap-2 min-w-0">
            <input type="radio" name="exec-agent" ${checked ? 'checked' : ''} ${detected ? '' : 'disabled'}
              onchange="onExecAgentRadioChange('${escapeHtml(agent.id)}')" />
            <div class="min-w-0">
              <div class="text-sm font-medium text-gray-900">${escapeHtml(agent.label || EXEC_AGENT_LABELS[agent.id] || agent.id)}</div>
              ${statusLine}
              <div class="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">${auth}${model}</div>
              <div class="mt-0.5 text-[11px] text-gray-500">连接测试：${escapeHtml(testMsg || '点击右侧「连接测试」')}</div>
              ${localCheckLine}
              ${installBlock}
              ${diagnosisBlock}
              ${modelStatusBlock}
            </div>
          </div>
          <div class="flex flex-col gap-1 items-end">
            <button type="button" ${detected ? '' : 'disabled'}
              class="shrink-0 text-xs px-2 py-1 border border-gray-300 hover:border-blue-400 text-gray-700 hover:text-blue-700 disabled:opacity-50"
              onclick="event.stopPropagation(); testExecAgent('${escapeHtml(agent.id)}')">连接测试</button>
            ${checkBtn}${switchBtn}
          </div>
        </div>
        <div class="text-xs mt-1.5 ${testClass}">${escapeHtml(testMsg)}</div>
      </label>`;
  }).join('');
}

function renderExecDrawer() {
  const source = _execPreferences?.exec_source || 'sample_io';
  const localRadio = document.getElementById('exec-source-local');
  const sampleRadio = document.getElementById('exec-source-sample');
  if (localRadio) localRadio.checked = source === 'local';
  if (sampleRadio) sampleRadio.checked = source !== 'local';

  const localSection = document.getElementById('exec-local-settings');
  localSection?.classList.toggle('hidden', source !== 'local');
  document.getElementById('exec-sample-disclaimer')?.classList.toggle('hidden', source !== 'sample_io');

  const consent = document.getElementById('exec-consent-checkbox');
  if (consent) consent.checked = !!_execPreferences?.consent_granted;

  const reason = document.getElementById('exec-ready-reason');
  if (reason) reason.textContent = getExecReadyReason();

  renderExecAgentModelSelectors();
  renderExecAgentCards();
  renderExecScanSummary();
}

async function fetchExecScan(silent = false) {
  const seq = ++_execScanSeq;
  _execScanLoading = true;
  renderExecScanSummary();
  renderExecAgentCards();
  try {
    const skillPath = getActiveSkillBundlePath();
    const qs = skillPath ? `?skill_bundle_path=${encodeURIComponent(skillPath)}` : '';
    const data = await apiFetch(`/api/exec/agents/scan${qs}`);
    if (seq !== _execScanSeq) return _execScanCache;
    _execScanCache = data || { scanned_at: null, agents: [] };
    renderExecBridgeIndicator();
    if (!silent) toast('Agent 扫描完成');
    return _execScanCache;
  } catch (e) {
    if (seq !== _execScanSeq) return _execScanCache;
    if (!silent) toast(`扫描 Agent 失败：${e.message}`, false);
    const summary = document.getElementById('exec-scan-summary');
    if (summary) {
      summary.className = 'text-xs text-red-700 leading-relaxed min-h-[1.25rem]';
      summary.textContent = `扫描失败：${e.message}`;
    }
    return _execScanCache;
  } finally {
    if (seq === _execScanSeq) {
      _execScanLoading = false;
      renderExecScanSummary();
      renderExecAgentModelSelectors();
      renderExecAgentCards();
      const reason = document.getElementById('exec-ready-reason');
      if (reason) reason.textContent = getExecReadyReason();
    }
  }
}

async function fetchExecPreferences(silent = false) {
  try {
    const wasReady = !!_execPreferences?.ready;
    const data = await apiFetch('/api/exec/preferences');
    _execPreferences = data || null;
    if (_execPreferences?.ready) _execBannerDismissed = false;
    renderExecBridgeIndicator();
    renderExecDrawer();
    renderExecBanner();
    if (!wasReady && _execPreferences?.ready && _pendingFormalResume) {
      renderMessages(_messagesCache);
      await resumePendingFormalEval();
    }
    return _execPreferences;
  } catch (e) {
    if (!silent) toast(`读取执行设置失败：${e.message}`, false);
    return _execPreferences;
  }
}

async function putExecPreferences(patch) {
  await apiFetch('/api/exec/preferences', {
    method: 'PUT',
    body: JSON.stringify(patch || {}),
  });
  await fetchExecPreferences(true);
  renderExecBridgeIndicator();
  renderExecDrawer();
  renderExecBanner();
}

async function onExecSourceRadioChange(nextSource) {
  if (!_execPreferences || _execPreferences.exec_source === nextSource) return;
  _execBannerDismissed = false;
  await putExecPreferences({ exec_source: nextSource });
}

async function onExecAgentRadioChange(nextAgent) {
  if (!_execPreferences || _execPreferences.exec_agent === nextAgent) return;
  await putExecPreferences({ exec_agent: nextAgent, exec_model: 'default' });
}

async function onExecAgentSelectChange(nextAgent) {
  if (!_execPreferences || _execPreferences.exec_agent === nextAgent) return;
  await putExecPreferences({ exec_agent: nextAgent, exec_model: 'default' });
}

async function onExecModelSelectChange(nextModel) {
  if (!_execPreferences || getSelectedExecModel() === nextModel) return;
  await putExecPreferences({ exec_model: nextModel || 'default' });
}

async function onExecConsentCheckbox(checked) {
  if (!checked) return;
  try {
    await apiFetch('/api/exec/consent', {
      method: 'POST',
      body: JSON.stringify({ granted: true }),
    });
    await fetchExecPreferences(true);
    renderExecBanner();
    toast('已记录本地执行同意');
  } catch (e) {
    const box = document.getElementById('exec-consent-checkbox');
    if (box) box.checked = false;
    toast(`同意失败：${e.message}`, false);
  }
}

async function rescanExecAgents() {
  await fetchExecScan();
  await fetchExecPreferences(true);
}

async function testExecAgent(agentId) {
  _execAgentTestStatus[agentId] = '测试中…';
  renderExecAgentCards();
  try {
    // D12: only validate the currently-selected model when testing the
    // currently-active agent card. Other cards keep testing the CLI default.
    const isActiveAgent = getSelectedExecAgent() === agentId;
    const modelToTest = isActiveAgent ? (_execPreferences?.exec_model || null) : null;
    const data = await apiFetch(`/api/exec/agents/${encodeURIComponent(agentId)}/test`, {
      method: 'POST',
      body: JSON.stringify(modelToTest ? { model: modelToTest } : {}),
    });
    const base = data?.message || (data?.ok ? '通过' : '失败');
    const timePart = Number.isFinite(data?.duration_ms) ? `（${data.duration_ms}ms）` : '';
    _execAgentTestStatus[agentId] = `${base}${timePart}`;
    // D5: a successful smoke test proves the agent is authenticated/usable —
    // optimistically flip the badge from "待测试" to "可用" without a real
    // auth probe (which can hang, e.g. `cursor-agent auth status` on Windows).
    // Resets on the next full re-scan.
    if (data?.ok) {
      const entry = (_execScanCache?.agents || []).find((a) => a.id === agentId);
      if (entry) entry.auth_status = 'ok';
    }
  } catch (e) {
    _execAgentTestStatus[agentId] = `失败：${e.message}`;
  }
  renderExecAgentCards();
}

async function runRuntimePreflightFromDetail(encodedPath, encodedRuntime, encodedModel) {
  await runLocalExecutionCheck(decodeURIComponent(encodedRuntime || ''), {
    skillPath: decodeURIComponent(encodedPath || ''),
    modelId: decodeURIComponent(encodedModel || 'default'),
  });
}

async function runLocalExecutionCheck(runtimeId, opts = {}) {
  const skillPath = opts.skillPath || getActiveSkillBundlePath();
  const modelId = opts.modelId || (getSelectedExecAgent() === runtimeId ? getSelectedExecModel() : 'default');
  if (!skillPath || !runtimeId) {
    toast('缺少环境检查参数', false);
    return null;
  }
  const key = `${runtimeId}:${modelId}:${skillPath}`;
  _runtimePreflightStatus[key] = { status: 'running' };
  try {
    const data = await apiFetch(`/api/exec/runtimes/${encodeURIComponent(runtimeId)}/preflight`, {
      method: 'POST',
      body: JSON.stringify({
        skill_bundle_path: skillPath,
        model: modelId,
        force: !!opts.force,
        regenerate_check_case: !!opts.regenerate,
      }),
    });
    _runtimePreflightStatus[key] = data;
    const msg = data?.message_zh || formatLocalCheckStatus({ local_check_status: data?.status, local_check_expires_at: data?.expires_at });
    const suffix = data?.status === 'passed'
      ? ''
      : '（仅作诊断，不会阻止正式评估；正式结果以 case 实跑为准）';
    toast(`本地执行环境检查：${msg}${suffix}`, data?.status === 'passed');
    await fetchExecScan(true);
    return data;
  } catch (e) {
    _runtimePreflightStatus[key] = { status: 'error', failure_reason: e.message };
    toast(`本地执行环境检查失败：${e.message}`, false);
    return null;
  }
}

function findVerifiedRuntimeModel(runtimeId) {
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const agent = agents.find((a) => a.id === runtimeId && a.can_switch_and_rerun);
  return agent?.selected_model || (getSelectedExecAgent() === runtimeId ? getSelectedExecModel() : 'default');
}

async function switchToVerifiedRuntime(runtimeId) {
  const skillPath = getActiveSkillBundlePath();
  if (!skillPath) {
    toast('请先填写 Bundle 路径', false);
    return;
  }
  try {
    const data = await apiFetch('/api/exec/runtimes/switch', {
      method: 'POST',
      body: JSON.stringify({
        runtime_id: runtimeId,
        model: findVerifiedRuntimeModel(runtimeId),
        skill_bundle_path: skillPath,
      }),
    });
    toast(data?.message_zh || '已切换本地工具', true);
    await fetchExecPreferences(true);
    await fetchExecScan(true);
  } catch (e) {
    toast(`切换失败：${e.message}`, false);
  }
}

function renderLocalExecCheckRecovery(d) {
  const codes = (d.report && d.report.reason_codes) || d.reason_codes || [];
  if (!codes.includes('LOCAL_RUNTIME_PREFLIGHT_REQUIRED')) return '';
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const alternates = agents.filter((a) => a.can_switch_and_rerun && a.id !== getSelectedExecAgent());
  return `<div class="mt-2 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded px-3 py-2 space-y-2">
    <div><strong>本地执行环境检查未通过。</strong>这是诊断结果，不代表正式评估一定失败；新版正式评估会以真实 case 执行为准。</div>
    <div class="flex flex-wrap gap-2">
      <button type="button" class="px-2 py-1 border border-amber-300 bg-white hover:bg-amber-100"
        onclick="runLocalExecutionCheck(getSelectedExecAgent(), { force: true })">重新检查</button>
      <button type="button" class="px-2 py-1 border border-amber-300 bg-white hover:bg-amber-100"
        onclick="runLocalExecutionCheck(getSelectedExecAgent(), { regenerate: true, force: true })">重置轻量检查</button>
      <button type="button" class="px-2 py-1 border border-amber-300 bg-white hover:bg-amber-100"
        onclick="switchExecBannerToSample()">使用样例输出评估（非本地真跑）</button>
      ${alternates.map((a) => `<button type="button" class="px-2 py-1 border border-emerald-300 bg-white hover:bg-emerald-50"
        onclick="switchToVerifiedRuntime('${escapeHtml(a.id)}')">改用已检查通过的 ${escapeHtml(a.label || a.id)}</button>`).join('')}
    </div>
  </div>`;
}

function startExecBridgePoll() {
  if (_execPollTimer) clearInterval(_execPollTimer);
  _execPollTimer = setInterval(async () => {
    await fetchExecPreferences(true);
    await fetchExecScan(true);
  }, 8000);
}

async function initExecBridge() {
  await fetchExecPreferences(true);
  await fetchExecScan(true);
  renderExecBridgeIndicator();
  renderExecDrawer();
  renderExecBanner();
  startExecBridgePoll();
}

function toggleDebugPanel() {
  document.getElementById('debug-panel').classList.toggle('hidden');
}

function resetConversationView() {
  _activeConversationId = null;
  _activeRunId = null;
  _latestConversationStatus = null;
  _messagesCache = [];
  _lastFetchedMessageCount = null;
  _lastFetchedMessagesRunId = null;
  _lastFetchedMessagesRunStatus = null;
  _pendingFormalResume = false;
  _pendingFormalAction = null;
  _openingTriggeredRunId = null;
  _conversationPollFailCount = 0;
  clearBridgePromptCard();
  stopConversationPolling();
  updateChatLiveRunPanel(null);
  const cidEl = document.getElementById('chat-conversation-id');
  if (cidEl) cidEl.textContent = '未选择会话';
}

function startConversationPolling() {
  stopConversationPolling();
  _conversationPollTimer = setInterval(() => pollConversation(), 3000);
}

function stopConversationPolling() {
  if (_conversationPollTimer) {
    clearInterval(_conversationPollTimer);
    _conversationPollTimer = null;
  }
}

function getStatusValue(status, keys, fallback = null) {
  for (const key of keys) {
    if (status && status[key] !== undefined && status[key] !== null) {
      return status[key];
    }
  }
  return fallback;
}

function isRunCompleted(statusObj) {
  const runStatus = getStatusValue(statusObj, ['run_status', 'active_run_status', 'status'], null);
  const runStartedAt = getStatusValue(statusObj, ['run_started_at', 'active_run_started_at'], '');
  if (!runStatus) return true;
  return !isRunActivelyExecuting(runStatus, runStartedAt);
}

async function fetchConversationStatus() {
  if (!_activeConversationId) return null;
  try {
    return await apiFetch(`/conversations/${encodeURIComponent(_activeConversationId)}/status`);
  } catch (_) {
    try {
      return await apiFetch(`/status?conversation_id=${encodeURIComponent(_activeConversationId)}`);
    } catch (_) {
      return null;
    }
  }
}

async function fetchConversationMessages() {
  if (!_activeConversationId) return [];
  let data = null;
  try {
    data = await apiFetch(`/conversations/${encodeURIComponent(_activeConversationId)}/messages`);
  } catch (_) {
    try {
      data = await apiFetch(`/messages?conversation_id=${encodeURIComponent(_activeConversationId)}`);
    } catch (_) {
      data = await apiFetch('/messages').catch(() => ({ messages: [] }));
    }
  }
  const raw = Array.isArray(data) ? data : (data.messages || data.items || []);
  return raw.filter(m => {
    const cid = m.conversation_id || m.session_id || _activeConversationId;
    return cid === _activeConversationId;
  });
}

function normalizeMessageRole(msg) {
  const role = String(msg.role || msg.sender || msg.type || '').toLowerCase();
  if (role.includes('assistant') || role.includes('agent')) return 'agent';
  if (role.includes('system')) return 'system';
  return 'user';
}

function normalizeMessageText(msg) {
  return msg.content || msg.message || msg.text || '';
}

function _messageDomKey(m) {
  const id = m.id != null ? String(m.id) : '';
  const runId = m.run_id || (m.payload_json && m.payload_json.run_id) || '';
  const mtype = m.message_type || 'text';
  return `${mtype}:${runId}:${id}:${normalizeMessageText(m).slice(0, 40)}`;
}

function formatGapMessageZh(gap) {
  if (!gap) return '—';
  let text = String(gap.message || gap.hint || gap.field_path || 'gap');
  const replacements = [
    [/eval_cases\//g, '评测案例目录'],
    [/\beval_cases\b/g, '评测案例'],
    [/sample_io\//g, '样例输入输出目录'],
    [/\bsample_io\b/g, '样例输入输出'],
    [/Capability 评审/g, '能力评估（双模型评审）'],
    [/\bCapability\b/g, '能力评估'],
    [/Level 1/g, '一级验证（样例输出比对）'],
    [/Level 2/g, '二级验证（脚本执行）'],
    [/SKILL\.md frontmatter/g, 'Skill 说明文件头部信息'],
    [/SKILL\.md/g, 'Skill 说明文件'],
    [/risk_level=(\w+)/g, (_, r) => `风险等级 ${RISK_LEVEL_ZH[r] || r}`],
    [/risk_level:\s*(\w+)/g, (_, r) => `风险等级 ${RISK_LEVEL_ZH[r] || r}`],
  ];
  for (const [pat, rep] of replacements) {
    text = text.replace(pat, rep);
  }
  return text;
}

function findGatePayloadBeforePlan(messages, planIdx) {
  if (planIdx <= 0) return null;
  const planPayload = (messages[planIdx] || {}).payload_json || {};
  if (planPayload.gate_snapshot) return planPayload.gate_snapshot;
  for (let i = planIdx - 1; i >= 0; i--) {
    const mt = (messages[i].message_type || 'text');
    if (mt === 'assessment_gate_result') return messages[i].payload_json || null;
    if (mt === 'propagation_plan') break;
  }
  return null;
}

function mergedGateMessageIndex(messages, latestPlanIndex) {
  if (latestPlanIndex <= 0) return -1;
  if (!findGatePayloadBeforePlan(messages, latestPlanIndex)) return -1;
  for (let i = latestPlanIndex - 1; i >= 0; i--) {
    const mt = (messages[i].message_type || 'text');
    if (mt === 'assessment_gate_result') return i;
    if (mt === 'propagation_plan') break;
  }
  return -1;
}

function renderMessages(messages) {
  const container = document.getElementById('chat-messages');
  if (!messages.length) {
    container.innerHTML = '<p class="text-sm text-gray-400 text-center py-16">暂无消息</p>';
    _lastRenderedMessageKeys = [];
    return;
  }
  const latestPlanIndex = messages.reduce((best, msg, idx) => {
    if ((msg.message_type || 'text') !== 'propagation_plan') return best;
    const version = Number((msg.payload_json || {}).plan_version || 0);
    if (best === -1) return idx;
    const bestVersion = Number(((messages[best] || {}).payload_json || {}).plan_version || 0);
    return version >= bestVersion ? idx : best;
  }, -1);
  const perspective = getPerspective();
  const keys = messages.map((m, idx) => {
    const base = _messageDomKey(m);
    if ((m.message_type || 'text') === 'propagation_plan') {
      const ver = (m.payload_json || {}).plan_version;
      return `${perspective}:${base}:plan-v${ver}:${idx === latestPlanIndex ? 'latest' : 'hist'}`;
    }
    return `${perspective}:${base}`;
  });
  if (
    _lastRenderedMessageKeys.length === keys.length
    && _lastRenderedMessageKeys.every((k, i) => k === keys[i])
  ) {
    refreshConversationLiveProgress();
    renderBridgePromptCard();
    return;
  }
  _lastRenderedMessageKeys = keys;
  const mergedGateIdx = mergedGateMessageIndex(messages, latestPlanIndex);
  container.innerHTML = messages.map((m, idx) => {
    const role = normalizeMessageRole(m);
    const text = normalizeMessageText(m);
    const mtype = m.message_type || 'text';
    if (idx === mergedGateIdx) return '';
    if (mtype === 'propagation_plan') {
      const isLatest = idx === latestPlanIndex;
      const gatePayload = isLatest ? findGatePayloadBeforePlan(messages, idx) : null;
      const inner = renderPropagationPlanHtml(m.payload_json || {}, { showActions: isLatest, gatePayload });
      const histCls = isLatest ? 'border-amber-200 bg-amber-50/70' : 'border-amber-100 bg-amber-50/40 opacity-95';
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border ${histCls} p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'propagation_summary') {
      const inner = renderPropagationSummaryHtml(m.payload_json || {});
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-emerald-200 bg-emerald-50/70 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'propagation_fork') {
      const inner = renderPropagationForkHtml(m.payload_json || {}, text);
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-indigo-200 bg-indigo-50/70 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'draft_preview') {
      const inner = renderDraftPreviewHtml(m.payload_json || {});
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-indigo-200 bg-indigo-50/70 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'draft_failed') {
      const inner = renderDraftFailedHtml(m.payload_json || {});
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-red-200 bg-red-50/70 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'local_execution_check'
      || (mtype === 'readiness_result' && (m.payload_json || {}).phase === 'local_execution_check')) {
      const inner = renderLocalExecutionCheckHtml(text, m.payload_json || {});
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-indigo-200 bg-indigo-50/70 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'readiness_result' || mtype === 'assessment_gate_result') {
      const inner = renderAssessmentGateHtml(m.payload_json || {});
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'security_blocked' && m.payload_json) {
      const intro = text
        ? `<p class="text-sm font-medium text-red-900 mb-2 leading-relaxed">${escapeHtml(text)}</p>`
        : '';
      const inner = intro + renderSecurityFindingsHtml(m.payload_json);
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-red-300 bg-red-50/60 p-3 text-sm">${inner}</div></div>`;
    }
    if (mtype === 'rich_report' && m.payload_json) {
      const inner = renderReportHtml(m.payload_json, _latestConversationStatus || {});
      return `<div class="flex justify-start"><div class="max-w-[95%] w-full rounded-2xl border border-indigo-200 bg-indigo-50/50 p-3 text-sm">${inner}</div></div>`;
    }
    if (role === 'system') {
      return `<div class="text-center text-xs text-gray-500 px-4">${escapeHtml(text)}</div>`;
    }
    const isUser = role === 'user';
    if (isUser && isInternalUserMessage(text)) return '';
    const st = _latestConversationStatus || {};
    const awaitingSkill = getStatusValue(st, ['status', 'conversation_status'], '') === 'awaiting_skill_id_confirm';
    const skillChips = (!isUser && awaitingSkill && text.includes('请回复') && text.includes('确认'))
      ? renderSkillIdConfirmChips(st.skill_id || '')
      : '';
    const agentBubbleCls = 'max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap bg-white border border-gray-200 border-l-[3px] border-l-blue-300 text-gray-800';
    const userBubbleCls = 'max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap bg-blue-600 text-white';
    return `
      <div class="flex ${isUser ? 'justify-end' : 'justify-start'}">
        <div class="${isUser ? userBubbleCls : agentBubbleCls}">
          ${escapeHtml(text)}
          ${skillChips}
        </div>
      </div>`;
  }).join('');
  if (_optimisticPending) {
    container.innerHTML += `
      <div class="flex justify-start" id="agent-pending-bubble">
        <div class="max-w-[95%] w-full rounded-2xl px-3 py-2 text-sm bg-gray-100 text-gray-600">
          <div class="italic animate-pulse" data-chat-pending-label>${escapeHtml(_optimisticPendingLabel || activityPhaseLabel('thinking'))}</div>
          ${renderConversationLiveProgressSlot(_latestConversationStatus)}
        </div>
      </div>`;
  }
  refreshConversationLiveProgress();
  renderBridgePromptCard();
  container.scrollTop = container.scrollHeight;
  updateComposerState();
}

function renderActionChips(actions, runId, opts = {}) {
  if (!actions || !actions.length) return '';
  const { excludeOpenDetail = false } = opts;
  const perspective = getPerspective();
  return `<div class="flex flex-wrap gap-2 mt-3 pt-2 border-t border-gray-200">${actions.map(a => {
    const aid = a.id || a.action || '';
    if (excludeOpenDetail && (aid === 'openRunDetail' || aid === 'open_run_detail')) return '';
    if (a.visible_in === 'expert' && perspective !== 'expert') return '';
    if (a.visible_in === 'author' && perspective !== 'author') return '';
    const disabled = !a.enabled;
    const cls = disabled
      ? 'opacity-40 cursor-not-allowed bg-gray-100 text-gray-500'
      : 'bg-white hover:bg-gray-50 text-gray-800 border-gray-300 cursor-pointer';
    return `<button type="button" ${disabled ? 'disabled' : ''}
      onclick="handleReportAction('${a.id}', '${runId}')"
      class="text-xs px-3 py-1.5 rounded-lg border ${cls}">${escapeHtml(a.label)}</button>`;
  }).join('')}</div>`;
}

function renderPropagationActionChips(hasL0Pending) {
  const confirmDisabled = !!hasL0Pending;
  const confirmCls = confirmDisabled
    ? 'opacity-40 cursor-not-allowed border-emerald-200 bg-emerald-50/50 text-emerald-700'
    : 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100';
  const l0Hint = confirmDisabled
    ? '<p class="w-full text-xs text-amber-800 mt-1">请先在上方「待澄清评估需求」中回复，再点自动出题。</p>'
    : '';
  return `
    <div class="flex flex-wrap gap-2 mt-3 pt-2 border-t border-amber-200 items-center">
      <button type="button" ${confirmDisabled ? 'disabled' : ''} onclick="handlePropagationAction('confirm')"
        class="text-xs px-3 py-1.5 rounded-full border ${confirmCls}">
        自动出题
      </button>
      <button type="button" onclick="handlePropagationAction('manual')"
        class="text-xs px-3 py-1.5 rounded-full border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
        我自己补
      </button>
    </div>
    <p class="mt-2 text-xs text-gray-500 leading-relaxed">
      <span class="text-gray-600">自动出题</span>：系统按上表在评估沙盒生成临时评测案例（约 1–3 分钟）。
      <span class="mx-1">·</span>
      <span class="text-gray-600">我自己补</span>：本地改好后重新上传 ZIP。
    </p>
    ${l0Hint}`;
}

function renderForkActionChips(fork) {
  if (fork === 'mode_choice') {
    return `<div class="flex flex-wrap gap-2 mt-2">
      <button type="button" onclick="sendConversationMessage('${ACTION_PROPAGATE}', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800">系统自动出题</button>
      <button type="button" onclick="sendConversationMessage('我想描述使用场景', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-indigo-300 bg-indigo-50 text-indigo-800">先描述场景</button>
    </div>`;
  }
  if (fork === 'scene_choice') {
    return `<div class="flex flex-wrap gap-2 mt-2">
      <button type="button" onclick="sendConversationMessage('${ACTION_DRAFT_WRITE_FILE}', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-indigo-300 bg-indigo-50 text-indigo-800">写进文件确认</button>
      <button type="button" onclick="sendConversationMessage('${ACTION_SCENE_PROPAGATE}', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800">理解后自动出题</button>
    </div>`;
  }
  return '';
}

function renderSkillIdConfirmChips(skillId) {
  const label = skillId ? `确认「${skillId}」` : '确认继续';
  return `<div class="flex flex-wrap gap-2 mt-2">
    <button type="button" onclick="sendConversationMessage('${ACTION_CONFIRM_SKILL}', true)"
      class="text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800">${escapeHtml(label)}</button>
    <button type="button" onclick="document.getElementById('chat-input').focus()"
      class="text-xs px-3 py-1.5 rounded-full border border-gray-300 bg-white text-gray-700">名称不对，我打字说明</button>
  </div>`;
}

function renderDraftPreviewHtml(payload) {
  if (!payload || typeof payload !== 'object') return '';
  const files = Array.isArray(payload.files_to_write) ? payload.files_to_write : [];
  const cases = Array.isArray(payload.cases_preview) ? payload.cases_preview : [];
  return `
    ${renderFlowStepBar(payload.flow_step)}
    <div class="text-sm font-semibold text-indigo-900">修改草案预览</div>
    ${payload.next_hint_zh ? `<p class="mt-1 text-xs text-gray-600">${escapeHtml(payload.next_hint_zh)}</p>` : ''}
    <div class="mt-2 text-xs">
      <div class="font-medium text-gray-700">将写入</div>
      <ul class="list-disc list-inside text-gray-600">${files.length ? files.map(f => `<li>${escapeHtml(f)}</li>`).join('') : '<li>—</li>'}</ul>
      ${cases.length ? `<div class="mt-2 font-medium text-gray-700">题目摘要</div>
        <ul class="list-disc list-inside text-gray-600 space-y-1">${cases.map(c => `<li>${escapeHtml(c.id || '')} · ${escapeHtml(c.user_intent || '')}</li>`).join('')}</ul>` : ''}
    </div>
    <div class="flex flex-wrap gap-2 mt-3 pt-2 border-t border-indigo-200">
      <button type="button" onclick="sendConversationMessage('${ACTION_DRAFT_CONFIRM}', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800">确认写入</button>
      <button type="button" onclick="document.getElementById('chat-input').focus()"
        class="text-xs px-3 py-1.5 rounded-full border border-gray-300 bg-white text-gray-700">继续修改</button>
    </div>`;
}

function renderDraftFailedHtml(payload) {
  return `
    <div class="text-sm font-semibold text-red-800">草案生成未成功</div>
    <p class="mt-1 text-xs text-gray-600">${escapeHtml(payload?.next_hint_zh || '请选择下一步')}</p>
    <div class="flex flex-wrap gap-2 mt-2">
      <button type="button" onclick="sendConversationMessage('再试一次', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-gray-300 bg-white">再试一次</button>
      <button type="button" onclick="sendConversationMessage('${ACTION_MANUAL_UPLOAD}', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-gray-300 bg-white">手动上传 ZIP</button>
      <button type="button" onclick="sendConversationMessage('${ACTION_PROPAGATE}', true)"
        class="text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800">自动出题</button>
    </div>`;
}

function renderL0QuestionHtml(q) {
  if (typeof q === 'string') {
    return `<li class="text-amber-900">${escapeHtml(q)}</li>`;
  }
  const label = q.label_zh || q.question_zh || q.key || '待澄清项';
  const question = q.question_zh && q.label_zh ? q.question_zh : '';
  const why = q.why_zh || '';
  const example = q.example_zh || '';
  const options = Array.isArray(q.options) ? q.options : [];
  const optionsHtml = options.length
    ? `<div class="mt-1 text-amber-700/90">可参考：${options.map(o => escapeHtml(o)).join(' · ')}</div>`
    : '';
  return `
    <li class="px-3 py-2.5 space-y-1 border-l-[3px] border-orange-400 bg-orange-50/60">
      <div class="font-semibold text-orange-950">${escapeHtml(label)}</div>
      ${question ? `<div class="text-orange-900/90">${escapeHtml(question)}</div>` : ''}
      ${why ? `<div class="text-orange-800/70 text-[11px]">作用：${escapeHtml(why)}</div>` : ''}
      ${example ? `<div class="text-orange-700/80 italic text-[11px]">${escapeHtml(example)}</div>` : ''}
      ${optionsHtml}
    </li>`;
}

function renderLocalExecutionCheckHtml(text, payload = {}) {
  const body = text || '正在检查本地执行环境，请稍候…';
  const detail = payload.detail_zh
    ? `<p class="mt-1 text-xs text-indigo-800/90">${escapeHtml(payload.detail_zh)}</p>`
    : `<p class="mt-1 text-xs text-indigo-800/90">连接测试只证明 CLI 能响应；此步骤会验证所选工具能读取当前 Skill、必要时检查入口文件并返回可评估结果。高风险 Skill 可能先准备轻量检查用例。</p>`;
  return `
    <div class="text-sm font-semibold text-indigo-950">本地执行环境检查</div>
    <div class="mt-2 px-3 py-2.5 border border-indigo-200 rounded-lg bg-indigo-50/90 text-xs text-indigo-900 leading-relaxed">
      ${escapeHtml(body)}
      ${detail}
    </div>`;
}

function renderAssessmentGatePassedHtml(payload) {
  if (shouldBlockFormalEval()) {
    _pendingFormalAction = _pendingFormalAction || ACTION_START_FORMAL;
    _pendingFormalResume = true;
    return `
      <div class="text-sm font-semibold text-slate-900">评估条件检查</div>
      <div class="mt-2 px-3 py-2.5 border border-amber-300 rounded-lg bg-amber-50/90 text-xs text-amber-900 leading-relaxed">
        <span class="font-semibold">正式评估已暂停</span>：本地执行未就绪。请先完成执行设置，系统将自动续跑。
      </div>
      <p class="mt-2 text-xs text-amber-800">正在监听本地执行状态…</p>
    `;
  }
  const optional = Array.isArray(payload.optional_gaps) ? payload.optional_gaps : [];
  const optionalNote = optional.length
    ? `<p class="mt-2 text-xs text-slate-500">另有 ${optional.length} 项可选改进，不影响本次正式评估。</p>`
    : '';
  const lastStage = currentRunStageToken(_latestConversationStatus || {});
  const progressText = evalProgressLabel(lastStage, getExecSource());
  return `
    <div class="text-sm font-semibold text-slate-900">评估条件检查</div>
    <div class="mt-2 px-3 py-2.5 border border-green-200 rounded-lg bg-green-50/90 text-xs text-green-900 leading-relaxed">
      <span class="font-semibold">评估需求已满足</span>，${escapeHtml(progressText)}
    </div>
    ${optionalNote}
    ${renderConversationLiveProgressSlot(_latestConversationStatus)}
  `;
}

function renderAssessmentGateHtml(payload, opts = {}) {
  if (!payload || typeof payload !== 'object') return '';
  if (payload.phase === 'local_execution_check') {
    return renderLocalExecutionCheckHtml('', payload);
  }
  const embedded = opts.embedded === true;
  if (payload.can_enter_formal && !embedded) {
    return renderAssessmentGatePassedHtml(payload);
  }
  const blocking = Array.isArray(payload.blocking_gaps) ? payload.blocking_gaps : [];
  const optional = Array.isArray(payload.optional_gaps)
    ? payload.optional_gaps
    : (Array.isArray(payload.gaps) ? payload.gaps.filter((g) => g.severity === 'warn' || g.severity === 'info') : []);
  const score = payload.completeness_score;
  const security = formatSecurityZh(payload, 'security');
  const riskLocked = formatSecurityZh(payload, 'risk');
  const caseGate = payload.case_gate || {};
  const gatePassed = caseGate.passed === true;
  const gateLabel = gatePassed ? '通过' : (caseGate.passed === false ? '未通过' : '—');
  const optionalOnly = payload.can_enter_formal && (payload.optional_gaps || []).length > 0;
  const showChoices = !embedded && optionalOnly
    && !isRunActivelyExecuting(
      getStatusValue(_latestConversationStatus || {}, ['run_status', 'status'], ''),
      getStatusValue(_latestConversationStatus || {}, ['run_started_at', 'active_run_started_at'], ''),
    );
  const optionalBlock = optional.length
    ? `<details class="mt-1"><summary class="cursor-pointer text-slate-600 font-medium text-xs">可选改进（${optional.length} 项，不阻断正式评估）</summary>
        <ul class="list-disc list-inside text-gray-600 mt-1 space-y-0.5 pl-1 text-xs">
          ${optional.map((g) => `<li>${escapeHtml(formatGapMessageZh(g))}</li>`).join('')}
        </ul></details>`
    : '';
  const securityFindingsBlock = renderSecurityFindingsHtml(payload);
  const blockingBlock = blocking.length
    ? `<div class="mt-2 p-2 border border-amber-200 rounded-lg bg-amber-50/60">
        <div class="text-xs font-medium text-amber-900 mb-1">须先处理</div>
        <ul class="list-disc list-inside text-xs text-amber-800 space-y-0.5">
          ${blocking.map((g) => `<li>${escapeHtml(formatGapMessageZh(g))}</li>`).join('')}
        </ul></div>`
    : '';

  if (embedded) {
    const secCls = securityStatusColorClass(payload);
    const gateColor = gatePassed ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold';
    return `
      <div class="text-xs font-medium text-slate-700 mb-2">评估条件检查</div>
      <div class="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        <span>完整度 <strong class="text-slate-800">${score != null ? score : '—'}</strong></span>
        <span>安全 <span class="${secCls}">${escapeHtml(String(security))}</span></span>
        <span>风险锁定 <span class="text-slate-800">${escapeHtml(String(riskLocked))}</span></span>
        <span>门槛 <span class="${gateColor}">${escapeHtml(gateLabel)}</span></span>
      </div>
      ${securityFindingsBlock}
      ${blockingBlock}
      ${optionalBlock}
    `;
  }

  return `
    <div class="text-sm font-semibold text-slate-900">${escapeHtml(payload.headline_zh || '评估条件检查')}</div>
    <div class="mt-2 space-y-2 text-xs">
      <div class="flex flex-wrap gap-x-5 gap-y-1 px-2 py-2 border border-slate-200 rounded-lg bg-white text-slate-700">
        <span>完整度 <strong>${score != null ? escapeHtml(String(score)) : '—'}</strong></span>
        <span>安全 <strong class="${securityStatusColorClass(payload)}">${escapeHtml(String(security))}</strong></span>
        <span>风险锁定 <strong>${escapeHtml(String(riskLocked))}</strong></span>
        <span>门槛 <strong class="${gatePassed ? 'text-green-700' : 'text-red-600'}">${escapeHtml(gateLabel)}</strong></span>
      </div>
      ${securityFindingsBlock}
      ${blockingBlock}
      ${optionalBlock}
      ${renderOptionalImprovementChips(showChoices)}
    </div>
  `;
}

function renderPropagationPlanHtml(payload, opts = {}) {
  if (!payload || typeof payload !== 'object') return '';
  const showActions = opts.showActions !== false;
  const gatePayload = opts.gatePayload || payload.gate_snapshot || null;
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const questions = Array.isArray(payload.l0_questions) ? payload.l0_questions : [];
  const hasL0Pending = questions.length > 0;
  const isHistorical = !showActions;
  const planVersion = '';
  const histBadge = isHistorical
    ? '<span class="text-xs font-normal text-gray-400 ml-1">（历史版本，仅供参考）</span>'
    : '';
  const degraded = payload.enrichment_status === 'degraded'
    ? `<p class="mt-1 text-xs text-amber-700">${escapeHtml(payload.enrichment_degraded_hint || '业务说明为通用模板')}</p>`
    : '';
  const introBlock = showActions ? `
    <div class="mb-3 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed">
      正式评估需要完整的评测案例与必要澄清。以下内容<strong>仅写入评估沙盒</strong>，不会修改你上传的原始 Skill 文件。
    </div>` : '';
  const gateBlock = gatePayload
    ? `<div class="mb-3 pb-3 border-b border-amber-200">${renderAssessmentGateHtml(gatePayload, { embedded: true })}</div>`
    : '';
  const tableDim = hasL0Pending && showActions ? 'opacity-60' : '';
  const table = rows.length ? `
    <div class="mt-1 ${tableDim}">
      <div class="text-xs font-semibold text-amber-900 mb-1.5">评测案例补充计划</div>
      <table class="w-full text-xs border border-amber-200 rounded-lg overflow-hidden table-fixed">
        <colgroup>
          <col style="width:22%">
          <col style="width:78%">
        </colgroup>
        <thead class="bg-amber-50/80 text-amber-900">
          <tr>
            <th class="px-2 py-1.5 text-left font-medium">场景 · 数量</th>
            <th class="px-2 py-1.5 text-left font-medium">补测方向 / 业务预期</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-amber-100">
          ${rows.map((row) => {
            const redline = isRedlineRow(row);
            const gapNum = formatGapCell(row);
            return `
            <tr>
              <td class="px-2 py-2 align-top">
                <div class="font-medium text-gray-900">${escapeHtml(row.type_zh || '—')}</div>
                <div class="text-gray-500 mt-0.5">×${escapeHtml(gapNum)}</div>
                ${redline ? renderRedlineNote(row) : ''}
              </td>
              <td class="px-2 py-2 align-top space-y-1">
                <div class="text-gray-700 leading-relaxed">${escapeHtml(row.tests_what || '—')}</div>
                ${row.business_expectation ? `<div class="text-gray-500 text-[11px] leading-relaxed border-t border-amber-50 pt-1">${escapeHtml(row.business_expectation)}</div>` : ''}
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>` : '<p class="mt-2 text-xs text-gray-500">暂无评测案例补充明细</p>';
  const l0Section = questions.length ? `
    <div class="mt-3 rounded-lg bg-orange-50 border-2 border-orange-300 shadow-sm overflow-hidden">
      <div class="px-3 pt-3 pb-2">
        <div class="text-xs font-bold text-orange-900 tracking-wide uppercase mb-1">待澄清评估需求</div>
        <p class="text-xs text-orange-800/80 leading-relaxed">
          请先回答下列问题，系统才能根据你的实际业务边界准确生成各类型评测案例。也可直接在对话框说明；有疑问可随时提问。
        </p>
      </div>
      <ul class="list-none text-xs divide-y divide-orange-200">
        ${questions.map(q => renderL0QuestionHtml(q)).join('')}
      </ul>
    </div>` : '';
  const cardTitle = showActions || gatePayload ? '评估材料补充' : '补题计划';
  return `
    ${renderFlowStepBar(payload.flow_step)}
    <div class="text-sm font-semibold text-amber-900 flex items-center flex-wrap gap-2">
      ${cardTitle}
      ${planVersion}
      ${histBadge}
    </div>
    ${introBlock}
    ${gateBlock}
    ${table}
    ${l0Section}
    ${degraded}
    ${showActions ? renderPropagationActionChips(hasL0Pending) : ''}
  `;
}

function renderPropagationForkHtml(payload, text) {
  const fork = payload?.fork || '';
  return `
    ${renderFlowStepBar(payload?.flow_step)}
    <div class="text-sm text-gray-800 whitespace-pre-wrap">${escapeHtml(text || '')}</div>
    ${payload?.next_hint_zh ? `<p class="mt-1 text-xs text-gray-500">${escapeHtml(payload.next_hint_zh)}</p>` : ''}
    ${renderForkActionChips(fork)}
  `;
}

function summarizeCasesByType(caseIds) {
  const patterns = [
    ['happy', '正常场景'],
    ['edge', '边界场景'],
    ['refusal', '拒绝场景'],
    ['adv', '对抗场景'],
  ];
  const counts = {};
  for (const raw of caseIds) {
    const lower = String(raw).toLowerCase();
    let label = '其他';
    for (const [pat, zh] of patterns) {
      if (lower.includes(pat)) { label = zh; break; }
    }
    counts[label] = (counts[label] || 0) + 1;
  }
  return Object.entries(counts).map(([typeZh, count]) => ({ type_zh: typeZh, count }));
}

function renderPropagationSummaryHtml(payload) {
  if (!payload || typeof payload !== 'object') return '';
  const casesWritten = Array.isArray(payload.cases_written) ? payload.cases_written : [];
  const typeSummary = Array.isArray(payload.type_summary) && payload.type_summary.length
    ? payload.type_summary
    : summarizeCasesByType(casesWritten);
  const nAdded = payload.n_added ?? casesWritten.length;
  const fallbackNote = payload.used_fallback
    ? '<p class="mt-1 text-xs text-amber-700">部分题目使用了模板兜底。</p>'
    : '';
  const typeLines = typeSummary.length
    ? typeSummary.map((row) => `<li>${escapeHtml(row.type_zh || '其他')} ×${row.count ?? 0}</li>`).join('')
    : '<li>—</li>';
  const techDetails = casesWritten.length
    ? `<details class="mt-2 text-xs">
        <summary class="cursor-pointer text-emerald-800 font-medium">技术明细（题目 ID）</summary>
        <ul class="list-disc list-inside text-gray-600 mt-1 space-y-0.5">${casesWritten.map(v => `<li>${escapeHtml(v)}</li>`).join('')}</ul>
      </details>`
    : '';
  return `
    <div class="text-sm font-semibold text-emerald-900">补题已完成</div>
    <p class="mt-1 text-xs text-gray-700">共生成 <strong>${nAdded}</strong> 道评估题。</p>
    ${fallbackNote}
    <div class="mt-2 p-2 bg-white border border-emerald-200 rounded-lg text-xs">
      <div class="font-medium text-emerald-800 mb-1">题型分布</div>
      <ul class="list-disc list-inside text-gray-700 space-y-0.5">${typeLines}</ul>
    </div>
    ${techDetails}
  `;
}

function renderOptionalImprovementChips(show) {
  if (!show) return '';
  return `
    <div class="mt-3 flex flex-wrap gap-2">
      <button type="button" onclick="sendConversationMessage('${ACTION_READINESS_DRAFT}', true)"
        class="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs hover:bg-indigo-700">对话补充说明</button>
      <button type="button" onclick="sendConversationMessage('${ACTION_MANUAL_UPLOAD}', true)"
        class="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs hover:bg-slate-50">我自己改 ZIP</button>
    </div>
    <p class="mt-2 text-xs text-slate-500">以上为可选改进；评估需求满足后将自动开始正式评估。</p>`;
}

async function handlePropagationAction(action) {
  if (action === 'confirm') {
    const latestGate = getLatestAssessmentGatePayload(_messagesCache);
    if (latestGate?.can_enter_formal) {
      if (shouldBlockFormalEval()) {
        showBridgePromptCard(ACTION_START_FORMAL);
        return;
      }
      await sendConversationMessage(ACTION_START_FORMAL, true);
      return;
    }
    await sendConversationMessage(ACTION_PROPAGATE, true);
    return;
  }
  if (action === 'manual') {
    await sendConversationMessage(ACTION_MANUAL_UPLOAD, true);
  }
}

async function handleReportAction(actionId, runId) {
  if (actionId === 'confirm_all') {
    await sendConversationMessage('__SYSTEM_ACTION_CONFIRM_ALL__', true);
    return;
  }
  if (actionId === 'expert_approve') {
    try {
      await apiFetch(`/eval/review/${runId}`, {
        method: 'POST',
        body: JSON.stringify({ action: 'approve', operator: 'self', comment: 'UI approve' }),
      });
      setPerspective('author');
      toast('已批准');
      await pollConversation({ force: true, forceMessages: true });
      await loadSessionList({ force: true });
    } catch (e) { toast(e.message, false); }
    return;
  }
  if (actionId === 'expert_reject') {
    const comment = prompt('驳回意见（可选）') || '';
    try {
      await apiFetch(`/eval/review/${runId}`, {
        method: 'POST',
        body: JSON.stringify({ action: 'reject', operator: 'self', comment }),
      });
      setPerspective('author');
      toast('已驳回，会话已解冻');
      await pollConversation({ force: true, forceMessages: true });
      await loadSessionList({ force: true });
    } catch (e) { toast(e.message, false); }
  }
}

function openReportFromChat(runId) {
  if (!runId) return;
  openRunDetail(runId, { origin: 'chat' });
}

function verdictBadgeClass(verdict) {
  const v = String(verdict || '');
  if (/未通过|失败|拒绝/.test(v)) return 'bg-red-100 text-red-700';
  if (v.includes('通过')) return 'bg-green-100 text-green-700';
  return 'bg-amber-100 text-amber-800';
}

function renderReportHtml(apiDetail, statusObj) {
  if (!apiDetail) return '';
  const reportPayload = apiDetail.report || {};
  const phase = apiDetail.report_phase || 'formal';
  const headline = apiDetail.headline_zh || '评估结果';
  const summary = apiDetail.summary_one_liner || '';
  const scoreLine = apiDetail.score_line_html;
  const runId = apiDetail.run_id || '';
  const verdict = apiDetail.verdict_zh || '';
  const nextAction = apiDetail.next_action_zh || '';
  const isFormal = phase === 'formal' || phase === 'formal_pending_review';
  const badgeCls = verdictBadgeClass(verdict);
  const verdictBadge = (isFormal && verdict)
    ? `<span class="badge ${badgeCls}">${escapeHtml(verdict)}</span>`
    : '';
  const actions = apiDetail.actions || [];
  const scoreBlock = scoreLine
    ? `<div class="mt-2 text-sm text-gray-800">${scoreLine}</div>`
    : '';
  const executionSourceUsed = apiDetail.execution_source_used || reportPayload.execution_source_used || '';
  const levelAchieved = apiDetail.level_achieved || reportPayload.level_achieved || '';
  const spotCheckEligible = Boolean(
    apiDetail.spot_check_eligible ?? reportPayload.spot_check_eligible ?? false,
  );
  const sourceBadge = executionSourceUsed === 'local_agent' || executionSourceUsed === 'local'
    ? '<span class="badge border border-green-600 text-green-800 bg-white">LOCAL AGENT</span>'
    : (executionSourceUsed === 'sample_io'
      ? '<span class="badge border border-gray-400 text-gray-700 bg-white">SAMPLE IO</span>'
      : '');
  const levelBadge = levelAchieved
    ? `<span class="badge border border-blue-200 text-blue-700 bg-blue-50">LEVEL ${escapeHtml(String(levelAchieved).toUpperCase())}</span>`
    : '';
  const spotBadge = spotCheckEligible
    ? '<span class="badge border border-amber-300 text-amber-800 bg-amber-50">待专家抽检</span>'
    : '';
  const outcomeStrip = (sourceBadge || levelBadge || spotBadge)
    ? `<div class="mt-2 flex flex-wrap gap-1.5">${sourceBadge}${levelBadge}${spotBadge}</div>`
    : '';
  const cta = runId && isFormal
    ? `<button type="button" onclick="openReportFromChat('${escapeHtml(runId)}')"
        class="mt-2 text-xs text-indigo-700 hover:text-indigo-900 font-medium">
        查看完整报告 →
      </button>`
    : '';
  const expertChips = phase === 'formal_pending_review'
    ? (getPerspective() === 'expert'
      ? renderActionChips(actions, runId, { excludeOpenDetail: true })
      : `<p class="mt-2 text-xs text-amber-800">待专家复核 — 请切换到右上角【专家】视角进行裁定。</p>`)
    : '';
  return `
    <div class="text-sm font-semibold text-indigo-900 flex items-center gap-2">${escapeHtml(headline)}${verdictBadge}</div>
    ${runId ? `<div class="run-ref text-[10px] text-gray-400 mt-0.5">${escapeHtml(runRefLabel(runId))}</div>` : ''}
    ${summary ? `<p class="mt-1 text-xs text-gray-700 leading-relaxed">${escapeHtml(summary)}</p>` : ''}
    ${(isFormal && nextAction) ? `<p class="mt-1 text-xs text-indigo-800">下一步：${escapeHtml(nextAction)}</p>` : ''}
    ${outcomeStrip}
    ${scoreBlock}
    ${cta}
    ${expertChips}
  `;
}

function renderReportSkeleton() {
  return `
    <div class="animate-pulse space-y-3">
      <div class="h-5 bg-gray-200 rounded w-2/3"></div>
      <div class="h-4 bg-gray-200 rounded"></div>
      <div class="h-4 bg-gray-200 rounded"></div>
      <div class="h-20 bg-gray-100 rounded"></div>
    </div>
    <p class="text-xs text-blue-500">评估进行中，正在刷新报告…</p>
  `;
}

function renderCompletenessStatusCard(statusObj, apiDetail) {
  const runStatus = getStatusValue(statusObj, ['run_status', 'active_run_status', 'status'], apiDetail?.status || '');
  const gapZero = !!getStatusValue(statusObj, ['gap_zero'], false);
  const caseGatePassed = !!getStatusValue(statusObj, ['case_gate_passed'], false);
  const autoConfirmed = !!getStatusValue(statusObj, ['auto_confirmed'], false);

  if (runStatus === 'awaiting_confirm') {
    return `
      <div class="p-3 border border-amber-200 rounded-lg bg-amber-50 text-sm">
        <div class="text-xs text-amber-700 mb-1">补全状态</div>
        <div class="font-medium text-amber-900">需要补全 — 尚未进入双模型质量评审</div>
        <p class="text-xs text-amber-800 mt-1">请按下方缺口清单修改 staging 后重新评估。</p>
      </div>`;
  }

  const lines = [];
  lines.push(gapZero
    ? '<span class="text-green-700">✓ 结构缺口已清零</span>'
    : '<span class="text-amber-800">○ 尚有结构缺口（见缺口列表）</span>');
  lines.push(caseGatePassed
    ? '<span class="text-green-700">✓ 题型门禁已通过</span>'
    : '<span class="text-amber-800">○ 题型门禁未通过</span>');
  if (autoConfirmed) {
    lines.push('<span class="text-green-700">✓ 已整包确认</span>');
  } else if (gapZero && caseGatePassed) {
    lines.push('<span class="text-blue-700">→ 可点击「整包确认」解锁 capability_full</span>');
  }

  if (runStatus === 'awaiting_human_review') {
    lines.push('<span class="text-amber-800">需专家复核，会话可能已冻结</span>');
  }

  return `
    <div class="p-3 border border-gray-200 rounded-lg bg-white text-sm">
      <div class="text-xs text-gray-500 mb-2">补全状态</div>
      <div class="space-y-1 text-xs">${lines.join('<br>')}</div>
    </div>`;
}

function securityStatusBadge(secStatus) {
  const cls = {
    passed: 'bg-green-100 text-green-700',
    warning: 'bg-amber-100 text-amber-800',
    blocked: 'bg-red-100 text-red-700',
    fail: 'bg-red-100 text-red-700',
  }[secStatus] || 'bg-gray-100 text-gray-600';
  const label = { passed: '通过', warning: '警告', blocked: '阻断', fail: '失败' }[secStatus] || secStatus;
  return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
}

function renderReportCards(apiDetail, statusObj) {
  const target = document.getElementById('author-report-cards');
  if (!target) return;
  if (!apiDetail) {
    target.innerHTML = '<p class="text-sm text-gray-400 text-center py-12">暂无报告数据</p>';
    return;
  }
  target.innerHTML = renderReportHtml(apiDetail, statusObj);
}

function updateComposerState() {
  const input = document.getElementById('chat-input');
  const zipInput = document.getElementById('chat-zip-file');
  const hintEl = document.getElementById('chat-send-msg');
  if (!input) return;
  const st = _latestConversationStatus || {};
  const frozen = st.status === 'frozen';
  const humanPending = st.run_status === 'awaiting_human_review';
  const authorBlocked = frozen || (humanPending && getPerspective() === 'author');
  input.disabled = authorBlocked;
  if (zipInput) zipInput.disabled = authorBlocked;
  if (hintEl) {
    hintEl.textContent = st.status === 'awaiting_propagation_confirm' || st.status === 'awaiting_propagation_clarify'
      ? '可回复：确认自动出题 / 我自己补（或直接在对话框提问、补充澄清）'
      : '';
  }
}

function updateChatStatusBanner(statusObj) {
  const banner = document.getElementById('chat-status-banner');
  const runStatus = getStatusValue(statusObj, ['run_status', 'active_run_status', 'status'], '');
  const runStartedAt = getStatusValue(statusObj, ['run_started_at', 'active_run_started_at'], '');
  const frozen = getStatusValue(statusObj, ['conversation_status', 'status'], '') === 'frozen' || !!statusObj?.frozen;
  const humanPending = runStatus === 'awaiting_human_review';
  const autoRuns = getStatusValue(statusObj, ['auto_run_count'], 0);
  const maxRuns = getStatusValue(statusObj, ['max_auto_runs'], 5);

  banner.className = 'hidden px-4 py-2 text-xs';
  if (frozen || humanPending) {
    banner.className = 'px-4 py-2 text-xs bg-amber-50 text-amber-800 border-b border-amber-100';
    banner.textContent = humanPending && getPerspective() === 'author'
      ? '需人工复核 — 作者视角只读。请切换到【专家】视角进行裁定。'
      : '会话已冻结，暂不可修改。';
  } else if (isRunActivelyExecuting(runStatus, runStartedAt)) {
    banner.className = 'px-4 py-2 text-xs bg-blue-50 text-blue-700 border-b border-blue-100';
    const last = currentRunStageToken(statusObj);
    const stageZh = stageLabelForExec(last, getExecSource());
    banner.innerHTML = `评估进行中…（${stageZh}）`;
  } else {
    banner.textContent = '';
  }
  document.getElementById('chat-run-badge').textContent = `${autoRuns}/${maxRuns}`;
  updateChatLiveRunPanel(statusObj);
  updateComposerState();
}

function updateConfirmButton(_statusObj) { /* chips in rich_report */ }

async function refreshReport(_statusObj) { /* reports in message stream */ }

function updateChatLocalCheckButton() {
  const btn = document.getElementById('chat-local-check-btn');
  if (!btn) return;
  const shouldShow = getExecSource() === 'local';
  const canRun = canRunCurrentLocalExecutionCheck();
  btn.classList.toggle('hidden', !shouldShow);
  btn.disabled = !canRun;
  btn.title = canRun
    ? '运行当前 Skill 的本地执行环境检查（仅诊断，不阻断正式评估）'
    : '需要选择本地 Agent，并让当前会话具备 Skill Bundle 路径';
}

async function triggerOpeningIfNeeded(statusObj) {
  const runId = getStatusValue(statusObj, ['active_run_id', 'run_id'], null);
  if (!runId || _openingTriggeredRunId === runId) return;
  if (!isRunCompleted(statusObj)) return;
  const agentCount = _messagesCache.filter(m => normalizeMessageRole(m) === 'agent').length;
  if (agentCount > 0) return;
  _openingTriggeredRunId = runId;
  await sendConversationMessage('__TRIGGER_AGENT_OPENING__', true);
}

async function pollConversation(opts = {}) {
  if (!_activeConversationId) return;
  if (_conversationPollInFlight && !opts.force) return;
  const convId = _activeConversationId;
  _conversationPollInFlight = true;
  try {
    const statusObj = await fetchConversationStatus();
    if (convId !== _activeConversationId) return;
    if (!statusObj) {
      _conversationPollFailCount += 1;
      if (_conversationPollFailCount >= 2) {
        const banner = document.getElementById('chat-status-banner');
        if (banner) {
          banner.className = 'px-4 py-2 text-xs bg-amber-50 text-amber-800 border-b border-amber-100';
          banner.textContent = `状态刷新失败，已连续失败 ${_conversationPollFailCount} 次。请确认 serve 是否仍在运行。`;
        }
      }
      return;
    }
    _conversationPollFailCount = 0;
    _lastConversationPollAt = new Date();
    _latestConversationStatus = statusObj;
    _activeRunId = statusObj.active_run_id || _activeRunId;
    updateChatStatusBanner(statusObj);
    updateChatLocalCheckButton();
    syncPendingFromRunStatus(statusObj);

    const messageCount = Number(getStatusValue(statusObj, ['lui_messages_count'], 0) || 0);
    const runId = String(getStatusValue(statusObj, ['active_run_id', 'run_id'], '') || '');
    const runStatus = String(getStatusValue(statusObj, ['run_status', 'active_run_status', 'status'], '') || '');
    const terminal = isRunCompleted(statusObj);
    const messagesChanged = messageCount !== _lastFetchedMessageCount;
    const shouldFetchMessages = opts.forceMessages
      || _messagesCache.length === 0
      || messagesChanged
      || runId !== _lastFetchedMessagesRunId
      || (terminal && runStatus !== _lastFetchedMessagesRunStatus);

    if (shouldFetchMessages) {
      _messagesCache = await fetchConversationMessages();
      if (convId !== _activeConversationId) return;
      _lastFetchedMessageCount = messageCount;
      _lastFetchedMessagesRunId = runId;
      _lastFetchedMessagesRunStatus = runStatus;
    }

    const convStatus = getStatusValue(statusObj, ['status', 'conversation_status'], '');
    if (
      ['awaiting_propagation_confirm', 'awaiting_propagation_clarify'].includes(String(convStatus))
      || _messagesCache.some((m) => (m.message_type || '') === 'propagation_plan')
    ) {
      _optimisticPending = false;
      _optimisticPendingLabel = '';
    }
    if (terminal) {
      _optimisticPending = false;
      _optimisticPendingLabel = '';
    }
    if (shouldFetchMessages || terminal) {
      renderMessages(_messagesCache);
    } else {
      refreshConversationLiveProgress();
      updateComposerState();
    }
    if (terminal || messagesChanged) {
      await loadSessionList({ force: terminal });
    } else {
      await loadSessionList();
    }
  } finally {
    _conversationPollInFlight = false;
  }
}

async function sendConversationMessage(text, silent = false, displayLabel = null) {
  if (!_activeConversationId) {
    toast('请先创建或选择会话', false);
    return;
  }
  const input = document.getElementById('chat-input');
  const payloadText = text || input.value.trim();
  const displayText = displayLabel || payloadText;
  const skipConflictCheck = _skipFormalConflictOnce;
  _skipFormalConflictOnce = false;
  if (isFormalActionMessage(payloadText)) {
    const gatePayload = getLatestAssessmentGatePayload(_messagesCache) || {};
    if (!skipConflictCheck && shouldShowExecConflictModal(gatePayload.execution_source)) {
      showExecConflictModal(payloadText);
      return;
    }
    if (shouldBlockFormalEval()) {
      showBridgePromptCard(payloadText);
      return;
    }
  }
  if (!text && input) {
    input.value = '';
  }
  const zipFile = _pendingZipFile;
  const demoOn = localStorage.getItem(DEMO_MODE_KEY) === 'true';
  const demoPath = document.getElementById('demo-local-path')?.value.trim() || '';
  if (!payloadText && !zipFile && !(demoOn && demoPath)) return;
  if (!silent && displayText) {
    _messagesCache = [..._messagesCache, { role: 'user', content: displayText, message_type: 'text' }];
    _optimisticPending = true;
    _optimisticPendingLabel = activityPhaseLabel(pendingPhaseForCurrentStatus());
    renderMessages(_messagesCache);
  } else if (silent && isInternalUserMessage(payloadText)) {
    _optimisticPending = true;
    _optimisticPendingLabel = activityPhaseLabel(activityPhaseForAction(payloadText));
    renderMessages(_messagesCache);
  }
  const msgEl = document.getElementById('chat-send-msg');
  msgEl.textContent = silent ? '' : '发送中…';
  let chatResp = null;
  try {
    if (zipFile) {
      const fd = new FormData();
      fd.append('message', payloadText);
      fd.append('bundle_zip', zipFile);
      chatResp = await apiFetch(`/conversations/${encodeURIComponent(_activeConversationId)}/chat`, {
        method: 'POST',
        body: fd,
      });
    } else if (demoOn && demoPath && !String(payloadText).startsWith('__')) {
      chatResp = await apiFetch(`/conversations/${encodeURIComponent(_activeConversationId)}/bootstrap`, {
        method: 'POST',
        body: JSON.stringify({
          source: 'local_ref',
          skill_bundle_path: demoPath,
          user_message: payloadText,
        }),
      });
    } else {
      chatResp = await apiFetch(`/conversations/${encodeURIComponent(_activeConversationId)}/chat`, {
        method: 'POST',
        body: JSON.stringify({ message: payloadText }),
      });
    }
    if (chatResp?.activity_phase && KEEP_PENDING_PHASES.has(chatResp.activity_phase)) {
      _optimisticPending = true;
      _optimisticPendingLabel = activityPhaseLabel(chatResp.activity_phase, _latestConversationStatus);
      renderMessages(_messagesCache);
    }
    if (chatResp?.staging_path && _activeConversationId) {
      rememberStagingPath(_activeConversationId, chatResp.staging_path);
      await fetchExecScan(true);
      updateChatLocalCheckButton();
      renderExecAgentCards();
    }
    _pendingZipFile = null;
    document.getElementById('chat-zip-file').value = '';
    document.getElementById('chat-zip-name').textContent = '';
    msgEl.textContent = '';
    if (!silent) toast('已发送');
    await pollConversation({ force: true, forceMessages: true });
  } catch (e) {
    _optimisticPending = false;
    _optimisticPendingLabel = '';
    msgEl.textContent = '';
    if (e.status === 403) toast('会话已冻结（403）', false);
    else if (e.status === 409) toast('评估进行中，请稍后（409）', false);
    else toast(e.message, false);
  }
}

async function sendChatMessage() {
  await sendConversationMessage();
}

async function sendConfirmAll() {
  await sendConversationMessage('__SYSTEM_ACTION_CONFIRM_ALL__', true);
}

function toast(msg, ok=true) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `fixed bottom-6 right-6 text-sm px-4 py-3 rounded-xl shadow-xl max-w-sm z-50 transition ${ok ? 'bg-gray-900 text-white' : 'bg-red-600 text-white'}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3500);
}

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const d = await apiFetch('/health');
    document.getElementById('api-status').textContent = '● 在线';
    document.getElementById('api-status').className = 'text-xs text-green-500';
  } catch {
    document.getElementById('api-status').textContent = '● 离线';
    document.getElementById('api-status').className = 'text-xs text-red-500';
  }
}

// ── Trigger run ───────────────────────────────────────────────────────────────
async function triggerRun() {
  const skillId    = document.getElementById('inp-skill-id').value.trim();
  const bundlePath = document.getElementById('inp-bundle-path').value.trim();
  const state      = document.getElementById('inp-bundle-state').value;
  const mode       = document.getElementById('inp-eval-mode').value;

  if (!skillId || !bundlePath) { toast('请填写 Skill ID 和 Bundle 路径', false); return; }

  const msgEl = document.getElementById('run-msg');
  msgEl.textContent = '发起中…';
  try {
    const data = await apiFetch('/eval/run', {
      method: 'POST',
      body: JSON.stringify({ skill_id: skillId, skill_bundle_path: bundlePath,
                              bundle_state: state, evaluation_mode: mode }),
    });
    _currentRunId = data.run_id;
    msgEl.textContent = `run_id: ${data.run_id.slice(0,8)}…`;
    document.getElementById('run-status-card').classList.remove('hidden');
    toast('评估任务已提交，轮询状态中…');
    startPolling(data.run_id);
  } catch (e) {
    msgEl.textContent = '';
    toast(e.message, false);
  }
}

// ── Status polling ────────────────────────────────────────────────────────────
function startPolling(runId) {
  stopPolling();
  _pollTimer = setInterval(() => pollStatus(runId), 4000);
  pollStatus(runId);
}

function stopPolling() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}

function getProviderSummary(d) {
  return d.provider_summary || (d.report && d.report.provider_summary) || null;
}

function getStageProgress(d) {
  return d.stage_progress || (d.report && d.report.stage_progress) || [];
}

function findLocalAgentBudget(reportLike) {
  const report = getReportPayload(reportLike || {});
  const progress = Array.isArray(report?.stage_progress)
    ? report.stage_progress
    : getStageProgress(reportLike || {});
  return progress.find((item) =>
    item && typeof item === 'object' && item.event === 'stage_budget' && item.stage === 'case_executing'
  ) || null;
}

function renderLocalAgentBudget(reportLike) {
  const budget = findLocalAgentBudget(reportLike);
  if (!budget || !budget.budget_s) return '';
  const started = budget.started_at ? Date.parse(budget.started_at) : NaN;
  const elapsed = Number.isFinite(started) ? Math.max(0, Math.floor((Date.now() - started) / 1000)) : 0;
  const total = Number(budget.budget_s) || 0;
  const remaining = Math.max(0, total - elapsed);
  return `<div class="text-xs text-blue-800 bg-blue-50 border border-blue-200 px-2 py-1 mt-2 rounded">
    本地 Agent 真跑中：已用 ${elapsed}s / 总预算 ${total}s / 剩余 ${remaining}s
  </div>`;
}

function getLocalAgentCaseEvents(reportLike) {
  const stages = getStageProgress(reportLike || {});
  return (Array.isArray(stages) ? stages : []).filter((item) =>
    item && typeof item === 'object' && String(item.event || '').startsWith('local_agent_case_')
  );
}

function summarizeLocalAgentCaseEvents(events) {
  const byCase = new Map();
  for (const event of events) {
    const caseId = String(event.case_id || '').trim();
    if (!caseId) continue;
    const row = byCase.get(caseId) || { case_id: caseId, case_type: event.case_type || '', events: [] };
    row.events.push(event);
    if (event.case_type) row.case_type = event.case_type;
    if (event.event === 'local_agent_case_started') {
      row.started_at = event.created_at || row.started_at;
      row.status = row.status || 'running';
    } else if (event.event === 'local_agent_case_succeeded') {
      row.status = 'succeeded';
      row.duration_ms = event.duration_ms;
      row.agent_label = event.agent_label;
      row.model_label = event.model_label;
    } else if (event.event === 'local_agent_case_failed') {
      row.status = 'failed';
      row.duration_ms = event.duration_ms;
      row.degrade_reason = event.degrade_reason;
      row.stderr_excerpt = event.stderr_excerpt;
      row.agent_label = event.agent_label;
      row.model_label = event.model_label;
    }
    byCase.set(caseId, row);
  }
  return Array.from(byCase.values());
}

function formatCaseDuration(row) {
  if (Number.isFinite(Number(row.duration_ms))) {
    return `${Math.max(0, Number(row.duration_ms) / 1000).toFixed(1)}s`;
  }
  const started = row.started_at ? Date.parse(row.started_at) : NaN;
  if (!Number.isFinite(started)) return '计时中';
  return `${Math.max(0, Math.floor((Date.now() - started) / 1000))}s`;
}

function renderLocalAgentCaseProgress(reportLike) {
  const rows = summarizeLocalAgentCaseEvents(getLocalAgentCaseEvents(reportLike));
  if (!rows.length) return '';
  const running = rows.filter((row) => row.status === 'running');
  const failed = rows.filter((row) => row.status === 'failed');
  const succeeded = rows.filter((row) => row.status === 'succeeded');
  const statusBadge = (row) => {
    if (row.status === 'succeeded') return '<span class="badge bg-green-100 text-green-700 border-green-200">完成</span>';
    if (row.status === 'failed') return '<span class="badge bg-red-100 text-red-700 border-red-200">本地执行失败</span>';
    return '<span class="badge bg-blue-100 text-blue-700 border-blue-200">当前正在执行</span>';
  };
  const rowsHtml = rows.map((row) => {
    const reason = row.degrade_reason ? (EXEC_READY_REASON_ZH[row.degrade_reason] || row.degrade_reason) : '';
    const stderr = row.stderr_excerpt ? `<div class="mt-1 text-[11px] text-red-700 break-all">${escapeHtml(row.stderr_excerpt)}</div>` : '';
    const meta = [row.case_type, row.agent_label, row.model_label].filter(Boolean).join(' · ');
    return `
      <div class="py-2 border-t border-blue-100 first:border-t-0">
        <div class="flex items-center justify-between gap-2">
          <div class="min-w-0">
            <div class="font-mono text-xs text-slate-800 break-all">${escapeHtml(row.case_id)}</div>
            ${meta ? `<div class="text-[11px] text-slate-500">${escapeHtml(meta)}</div>` : ''}
          </div>
          <div class="flex items-center gap-2 shrink-0">
            ${statusBadge(row)}
            <span class="font-mono text-xs text-slate-500">${escapeHtml(formatCaseDuration(row))}</span>
          </div>
        </div>
        ${reason ? `<div class="mt-1 text-xs text-red-800">${escapeHtml(reason)}</div>` : ''}
        ${stderr}
      </div>`;
  }).join('');
  return `
    <section class="mt-2 border border-blue-200 bg-blue-50/60 rounded">
      <div class="px-3 py-2 flex items-center justify-between gap-3 flex-wrap">
        <h4 class="text-sm font-semibold text-blue-950">本地 Agent case 进度</h4>
        <div class="text-xs text-blue-800">执行中 ${running.length} / 完成 ${succeeded.length} / 失败 ${failed.length}</div>
      </div>
      <div class="px-3 pb-2 max-h-56 overflow-y-auto">${rowsHtml}</div>
    </section>`;
}

function renderConversationLocalAgentProgressContent(statusObj) {
  if (getExecSource() !== 'local') return '';
  const status = statusObj || {};
  const budgetHtml = renderLocalAgentBudget(status);
  const caseHtml = renderLocalAgentCaseProgress(status);
  if (!budgetHtml && !caseHtml) return '';
  return `${budgetHtml}${caseHtml}`;
}

function renderChatLiveRunPanelContent(statusObj) {
  const status = statusObj || {};
  const runStatus = getStatusValue(status, ['run_status', 'active_run_status', 'status'], '');
  const runStartedAt = getStatusValue(status, ['run_started_at', 'active_run_started_at'], '');
  if (!isRunActivelyExecuting(runStatus, runStartedAt)) return '';
  const stage = currentRunStageToken(status);
  const title = stageLabelForExec(stage, getExecSource()).replace(/<[^>]*>/g, '');
  const detail = evalProgressLabel(stage, getExecSource());
  const localProgress = renderConversationLocalAgentProgressContent(status);
  const refreshed = _lastConversationPollAt ? formatClockTime(_lastConversationPollAt) : '';
  return `
    <div class="px-4 py-2 border-b border-blue-100 bg-blue-50/80 text-sm text-blue-950 max-h-[40vh] overflow-y-auto">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="font-semibold">当前阶段：${escapeHtml(title)}</div>
        <div class="flex items-center gap-3 text-xs text-blue-700">
          ${refreshed ? `<span>最后刷新 ${escapeHtml(refreshed)}</span>` : ''}
          <span class="font-mono">${escapeHtml(String(getStatusValue(status, ['active_run_id', 'run_id'], '') || '').slice(0, 8))}${getStatusValue(status, ['active_run_id', 'run_id'], '') ? '…' : ''}</span>
        </div>
      </div>
      <div class="mt-1 text-xs text-blue-900 leading-relaxed">${escapeHtml(detail)}</div>
      ${localProgress}
    </div>`;
}

function ensureChatLiveRunPanel() {
  let panel = document.getElementById('chat-live-run-panel');
  if (panel) return panel;
  const banner = document.getElementById('chat-status-banner');
  if (!banner || !banner.parentElement) return null;
  panel = document.createElement('div');
  panel.id = 'chat-live-run-panel';
  panel.className = 'hidden';
  banner.insertAdjacentElement('afterend', panel);
  return panel;
}

function updateChatLiveRunPanel(statusObj) {
  const panel = ensureChatLiveRunPanel();
  if (!panel) return;
  const html = renderChatLiveRunPanelContent(statusObj);
  panel.innerHTML = html;
  panel.classList.toggle('hidden', !html);
}

function renderConversationLiveProgressSlot(statusObj) {
  const html = renderConversationLocalAgentProgressContent(statusObj);
  return `<div data-chat-live-run-progress class="${html ? '' : 'hidden'}">${html}</div>`;
}

function refreshConversationLiveProgress() {
  const html = renderConversationLocalAgentProgressContent(_latestConversationStatus);
  document.querySelectorAll('[data-chat-live-run-progress]').forEach((el) => {
    el.innerHTML = html;
    el.classList.toggle('hidden', !html);
  });
  const pendingLabel = document.querySelector('[data-chat-pending-label]');
  if (pendingLabel && _optimisticPending) {
    pendingLabel.textContent = _optimisticPendingLabel || activityPhaseLabel('thinking', _latestConversationStatus);
  }
}

let _usageDetailSeq = 0;
const _usageDetailStash = {};

function _bucketUsageRows(rows) {
  const bucket = (label) => ({ label, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 });
  const buckets = {
    local: bucket('本地 Agent'),
    providerA: bucket('Provider A · DeepSeek'),
    providerB: bucket('Provider B · Gemini'),
    other: bucket('其他'),
  };
  for (const row of rows) {
    const label = String(row.provider_label || '');
    let key = 'other';
    if (row.stage === 'local_agent') key = 'local';
    else if (/deepseek/i.test(label)) key = 'providerA';
    else if (/gemini/i.test(label)) key = 'providerB';
    const b = buckets[key];
    b.prompt_tokens += Number(row.prompt_tokens || 0);
    b.completion_tokens += Number(row.completion_tokens || 0);
    b.total_tokens += Number(row.total_tokens || 0);
  }
  return buckets;
}

/** D6: compact by default (总计 + 3 buckets), full per-stage table on demand via a modal. */
function renderUsageSummary(reportLike) {
  const report = getReportPayload(reportLike || {});
  const summary = report?.usage_summary || reportLike?.usage_summary;
  if (!summary || !summary.totals) return '';
  const rows = Array.isArray(summary.by_stage) ? summary.by_stage : [];
  const total = Number(summary.totals.total_tokens || 0);
  const prompt = Number(summary.totals.prompt_tokens || 0);
  const completion = Number(summary.totals.completion_tokens || 0);
  const partial = summary.partial ? '<span class="text-amber-700 ml-2">部分调用未返回 usage</span>' : '';
  const buckets = _bucketUsageRows(rows);

  const id = `u${++_usageDetailSeq}`;
  _usageDetailStash[id] = rows;

  const bucketChip = (b) => b.total_tokens
    ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-50 border border-gray-200 rounded text-gray-700">${escapeHtml(b.label)} <strong class="font-mono">${b.total_tokens}</strong></span>`
    : '';

  return `
    <section class="mt-4 border border-gray-200 bg-white rounded">
      <div class="px-3 py-2 flex items-center justify-between gap-3 flex-wrap">
        <h4 class="text-sm font-semibold text-gray-900">Token 消耗</h4>
        <button type="button" onclick="openUsageDetailModal('${id}')" class="text-xs text-blue-600 hover:underline">查看明细 →</button>
      </div>
      <div class="px-3 pb-3 flex flex-wrap items-center gap-2 text-xs">
        <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-200 rounded text-blue-800">总计 <strong class="font-mono">${total}</strong>（输入 ${prompt} / 输出 ${completion}）</span>
        ${bucketChip(buckets.providerA)}
        ${bucketChip(buckets.providerB)}
        ${bucketChip(buckets.local)}
        ${bucketChip(buckets.other)}
        ${partial}
      </div>
    </section>`;
}

function openUsageDetailModal(id) {
  const rows = _usageDetailStash[id] || [];
  const body = rows.length
    ? rows.map((row) => `
      <tr class="border-t border-gray-100">
        <td class="py-1 pr-2">${escapeHtml(row.stage || '-')}</td>
        <td class="py-1 pr-2">${escapeHtml(row.provider_label || '-')}</td>
        <td class="py-1 pr-2">${escapeHtml(row.model || '-')}</td>
        <td class="py-1 pr-2">${escapeHtml(row.case_id || '-')}</td>
        <td class="py-1 text-right">${Number(row.prompt_tokens || 0)}</td>
        <td class="py-1 text-right">${Number(row.completion_tokens || 0)}</td>
        <td class="py-1 text-right">${Number(row.total_tokens || 0)}</td>
      </tr>`).join('')
    : '<tr><td colspan="7" class="py-2 text-gray-400">暂无分阶段 usage 明细</td></tr>';
  const modalBody = document.getElementById('usage-detail-modal-body');
  if (!modalBody) return;
  modalBody.innerHTML = `
    <table class="w-full text-xs text-left">
      <thead class="text-gray-500">
        <tr>
          <th class="py-1 pr-2">阶段</th>
          <th class="py-1 pr-2">Provider</th>
          <th class="py-1 pr-2">模型</th>
          <th class="py-1 pr-2">Case</th>
          <th class="py-1 text-right">输入</th>
          <th class="py-1 text-right">输出</th>
          <th class="py-1 text-right">总计</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>`;
  document.getElementById('usage-detail-modal').classList.remove('hidden');
}

function closeUsageDetailModal() {
  document.getElementById('usage-detail-modal')?.classList.add('hidden');
}

function getTimingSummary(d) {
  if (d.timing_summary && Object.keys(d.timing_summary).length) {
    return d.timing_summary;
  }
  return {};
}

function normalizeReportView(d) {
  return {
    status: d.status,
    score_total: d.score_total,
    score_total_source: d.score_total_source || (d.report && d.report.score_total_source),
    reason_codes: (d.report && d.report.reason_codes) || d.reason_codes || [],
  };
}

/** T6: one-line score for history table cells */
function formatScoreCompact(d) {
  const v = normalizeReportView(d);
  if (v.status === 'awaiting_confirm') {
    return '<span class="text-amber-700">待补全</span>';
  }
  if (v.reason_codes.includes('EVAL_WORKFLOW_TIMEOUT')) {
    return '<span class="text-red-600">超时</span>';
  }
  if (v.reason_codes.includes('LOCAL_EXEC_UNAVAILABLE') || v.reason_codes.includes('LOCAL_EXEC_ALL_CASES_FAILED')) {
    return '<span class="text-red-600">本地执行阻断</span>';
  }
  if (v.score_total_source === 'null_due_to_disagreement') {
    return '<span class="text-amber-800">R5 分歧</span>';
  }
  if (v.score_total !== null && v.score_total !== undefined) {
    return `<span class="font-mono">${v.score_total}/100</span>`;
  }
  return '<span class="text-gray-400">—</span>';
}

function formatTimingSummaryCell(summary) {
  // stage_timing helper — used by history table cell
  if (!summary || !summary.total_phase_ms) {
    return '<span class="text-gray-400">—</span>';
  }
  const total = (summary.total_phase_ms / 1000).toFixed(1);
  const mj = summary.model_judging_ms != null
    ? `<div class="text-gray-400">评审 ${(summary.model_judging_ms / 1000).toFixed(1)}s</div>`
    : '';
  return `<span class="font-mono text-gray-800">${total}s</span>${mj}`;
}

const STAGE_LABELS = {
  level0_checking: 'Level0',
  risk_locking: 'Risk',
  case_executing: 'Case',
  code_asserting: '断言',
  model_judging: '双模评审',
  aggregating: '聚合',
};

function renderStageProgressList(stages) {
  if (!stages || !stages.length) return '';
  const stageNames = stages.filter(s => typeof s === 'string');
  const chips = stageNames.map(s => {
    const label = STAGE_LABELS[s] || s;
    return `<span class="inline-block mr-1 mb-1 px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">${escapeHtml(label)}</span>`;
  }).join('<span class="text-gray-300 mx-0.5">→</span>');
  if (!chips) return '';
  return `<div class="mt-2 text-xs">
    <span class="font-medium text-gray-600">阶段轨迹：</span>
    <div class="mt-1 flex flex-wrap items-center">${chips}</div>
  </div>`;
}

function renderStageTimingPanel(summary, opts = {}) {
  if (!summary || !summary.phases || !summary.phases.length) {
    return '';
  }
  const compact = opts.compact;
  const maxMs = Math.max(...summary.phases.map(p => p.ms), 1);
  const bars = summary.phases.map(p => {
    const label = p.label || STAGE_LABELS[p.stage] || p.stage;
    const pct = Math.max(6, Math.round((p.ms / maxMs) * 100));
    return `
      <div class="flex items-center gap-2 text-xs">
        <span class="w-20 text-gray-600 shrink-0">${escapeHtml(label)}</span>
        <div class="flex-1 h-2 bg-gray-100 rounded overflow-hidden">
          <div class="h-full bg-blue-500 rounded" style="width:${pct}%"></div>
        </div>
        <span class="w-12 text-right font-mono text-gray-700">${(p.ms / 1000).toFixed(2)}s</span>
      </div>`;
  }).join('');
  const slow = (!compact && summary.slow_cases && summary.slow_cases.length)
    ? `<div class="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-500">
        <span class="font-medium text-gray-600">慢 case：</span>
        ${summary.slow_cases.map(c =>
          `${escapeHtml(c.case_id)} ${(c.ms / 1000).toFixed(2)}s`
        ).join(' · ')}
      </div>`
    : '';
  const total = summary.total_phase_ms
    ? `<div class="text-xs text-gray-500 mt-2">管线合计 <strong class="text-gray-800">${(summary.total_phase_ms / 1000).toFixed(2)}s</strong></div>`
    : '';
  return `<div class="space-y-1">${bars}${slow}${total}</div>`;
}

function classifyProviderError(errorText) {
  const text = String(errorText || '').toLowerCase();
  if (/429|rate limit|too many requests|quota/.test(text)) return 'rate_limit';
  if (/region|country|unsupported location|not available/.test(text)) return 'region_unavailable';
  if (/api key|apikey|unauthorized|401|403|model.*not found|invalid.*model|permission/.test(text)) return 'auth_or_model';
  if (/timeout|timed out|deadline/.test(text)) return 'timeout';
  return 'unknown';
}

function providerErrorZh(errorText) {
  const kind = classifyProviderError(errorText);
  if (kind === 'rate_limit') return '模型服务限流或配额不足，请稍后重试。';
  if (kind === 'region_unavailable') return '模型服务在当前地区或网络环境不可用，请更换可用服务或网络。';
  if (kind === 'auth_or_model') return '模型密钥、权限或模型名称配置有误，请检查 Provider 设置。';
  if (kind === 'timeout') return '模型响应超时，请稍后重试或调大超时配置。';
  return '模型服务暂不可用，请查看错误详情。';
}

function renderProviderErrorPanel(d) {
  const errs = d.provider_errors
    || (d.report && d.report.evidence && d.report.evidence.filter(e => e.kind === 'provider_error'))
    || [];
  const codes = (d.report && d.report.reason_codes) || d.reason_codes || [];
  if (!errs.length && !codes.includes('EVAL_PROVIDER_UNAVAILABLE')) return '';
  const firstError = errs.find(e => e && (e.error || e.message)) || {};
  const errorText = firstError.error || firstError.message || '';
  const helpText = providerErrorZh(errorText);
  const rows = errs.slice(0, 12).map(e =>
    `<li class="text-xs text-red-800 py-0.5">${escapeHtml(e.provider || '?')} · ${escapeHtml(e.case_id || '?')} — ${escapeHtml(e.error || 'unknown')}</li>`
  ).join('');
  return `
    <div class="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm">
      <div class="font-medium text-red-800">双模型评审未产出分数</div>
      <p class="text-xs text-red-700 mt-1">${escapeHtml(helpText)}</p>
      ${rows ? `<ul class="mt-2 list-disc list-inside">${rows}</ul>` : ''}
    </div>`;
}

function renderSkillSummaryCard(d, opts = {}) {
  const report = getReportPayload(d);
  const ss = report.skill_summary || (d.skill_summary);
  if (!ss || typeof ss !== 'object') return '';
  const { collapsed = true } = opts;

  const verdict = ss.overall_verdict
    ? `<div class="bg-slate-100 rounded-lg px-3 py-2 text-base font-semibold text-slate-800 mb-2">${escapeHtml(ss.overall_verdict)}</div>`
    : '';

  const strItems = (ss.strengths || []).map(s =>
    `<div class="text-xs bg-green-50 text-green-800 rounded-md px-2 py-1">✓ ${escapeHtml(s)}</div>`).join('');
  const weakItems = (ss.weaknesses || []).map(w =>
    `<div class="text-xs bg-red-50 text-red-800 rounded-md px-2 py-1">✗ ${escapeHtml(w)}</div>`).join('');
  const swGrid = (strItems || weakItems) ? `
    <div class="grid grid-cols-2 gap-2 mb-2">
      <div>${strItems ? `<div class="text-xs font-semibold text-green-700 mb-1">亮点</div>${strItems}` : ''}</div>
      <div>${weakItems ? `<div class="text-xs font-semibold text-red-700 mb-1">不足</div>${weakItems}` : (strItems ? `<div class="text-xs font-semibold text-gray-500 mb-1">不足</div><div class="text-xs text-gray-500">暂无显著不足</div>` : '')}</div>
    </div>` : '';

  const dims = ss.dimension_notes || {};
  const dimRows = Object.entries({
    instruction_following: '指令遵循',
    output_compliance: '输出合规',
    business_resolution: '业务解决',
  }).map(([k, label]) => dims[k]
    ? `<div class="text-xs text-gray-600 py-0.5"><span class="font-medium text-gray-700">${label}：</span>${escapeHtml(dims[k])}</div>`
    : '').join('');

  const rec = ss.recommendation
    ? `<div class="bg-blue-50 border-l-4 border-blue-400 px-3 py-2 text-xs text-blue-800 mt-2">
        <span class="font-medium">建议：</span>${escapeHtml(ss.recommendation)}
       </div>`
    : '';

  const body = `<div class="space-y-1">${verdict}${swGrid}${dimRows ? `<div class="mt-1">${dimRows}</div>` : ''}${rec}</div>`;

  return `
    <details class="mt-3 border border-indigo-200 rounded-lg bg-indigo-50"${collapsed ? '' : ' open'}>
      <summary class="cursor-pointer px-3 py-2 text-sm font-semibold text-indigo-800 select-none">
        技能质量诊断摘要（AI 生成）▼
      </summary>
      <div class="px-3 pb-3">${body}</div>
    </details>`;
}

function renderLevel0Evidence(d) {
  const ev = (getReportPayload(d).evidence || []).filter(e => e.field && e.detail);
  if (!ev.length) return '';
  const items = ev.map(e =>
    `<li class="text-xs text-red-800"><code class="text-red-600">${escapeHtml(e.field)}</code> — ${escapeHtml(e.detail)}</li>`
  ).join('');
  return `<div class="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
    <div class="text-xs font-medium text-red-800 mb-1">Level0 诊断详情</div>
    <ul class="list-disc list-inside space-y-0.5">${items}</ul>
  </div>`;
}

function renderNarrativeCard(d) {
  const report = getReportPayload(d);
  const nar = report.narrative;
  if (!nar || !nar.headline_zh) return '';
  const reasons = (nar.reasons_zh || []).map(r =>
    `<li class="text-xs text-gray-700 py-0.5">${escapeHtml(r)}</li>`).join('');
  const actions = (nar.next_actions_zh || []).map(a =>
    `<li class="text-xs text-blue-800 py-0.5">${escapeHtml(a)}</li>`).join('');
  return `
    <div class="mt-3 p-3 bg-slate-50 border border-slate-200 rounded-lg">
      <div class="text-xs font-semibold text-slate-500 mb-1">运营结论</div>
      <div class="text-sm font-semibold text-slate-900">${escapeHtml(nar.headline_zh)}</div>
      ${nar.score_display_zh ? `<div class="text-xs text-slate-600 mt-1">${escapeHtml(nar.score_display_zh)}</div>` : ''}
      ${reasons ? `<ul class="mt-2 list-disc list-inside">${reasons}</ul>` : ''}
      ${actions ? `<div class="mt-2 text-xs font-medium text-slate-700">建议下一步</div><ul class="list-disc list-inside">${actions}</ul>` : ''}
    </div>`;
}

function renderDisagreementCard(d) {
  const db = getReportPayload(d).disagreement_brief;
  if (!db || !db.triggered) return '';
  const hints = (db.stage_hints_zh || []).map(h =>
    `<li class="text-xs text-amber-800 py-0.5">${escapeHtml(h)}</li>`).join('');
  const cases = (db.focused_cases || []).map(c =>
    `<li class="text-xs text-gray-700 py-0.5">${escapeHtml(c.case_id)}：DS ${c.deepseek_score ?? '—'} / GM ${c.gemini_score ?? '—'}（Δ ${c.gap ?? '—'}）· ${escapeHtml(c.hint_zh || '')}</li>`
  ).join('');
  return `
    <details class="mt-3 border border-amber-300 rounded-lg bg-amber-50" open>
      <summary class="cursor-pointer px-3 py-2 text-sm font-semibold text-amber-900">模型分歧说明（业务向）▼</summary>
      <div class="px-3 pb-3 space-y-2">
        <p class="text-sm text-amber-950">${escapeHtml(db.summary_zh || '')}</p>
        ${hints ? `<ul class="list-disc list-inside">${hints}</ul>` : ''}
        ${cases ? `<div class="text-xs font-medium text-gray-700 mt-1">分歧集中用例</div><ul class="list-disc list-inside">${cases}</ul>` : ''}
      </div>
    </details>`;
}

function renderRiskLockCard(d) {
  const rp = getReportPayload(d).risk_lock_provenance;
  if (!rp || !rp.locked) return '';
  const chain = [
    `自报 <strong>${escapeHtml(rp.declared)}</strong>`,
    `规则 <strong>${escapeHtml(rp.rule_scanned)}</strong>`,
    rp.ai_reviewed ? `AI <strong>${escapeHtml(rp.ai_reviewed)}</strong>` : null,
    `锁定 <strong class="text-green-900">${escapeHtml(rp.locked)}</strong>`,
  ].filter(Boolean).join(' → ');
  return `<div class="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
    <div class="text-xs font-semibold text-green-800 mb-1">风险溯源</div>
    <div class="text-xs text-green-900">${chain}</div>
    ${rp.ai_evidence_zh ? `<div class="text-xs text-gray-600 mt-1">${escapeHtml(rp.ai_evidence_zh)}</div>` : ''}
  </div>`;
}

function renderHumanReviewVerdict(d) {
  const hr = (getReportPayload(d).human_review) || {};
  if (!hr.reviewer_action) return '';
  const label = hr.reviewer_action === 'approve' ? '批准通过' : '驳回';
  return `<div class="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-800">
    <span class="font-medium">专家裁定：${label}</span>
    ${hr.operator ? ` · ${escapeHtml(hr.operator)}` : ''}
    ${hr.comment ? ` <span class="text-indigo-600">${escapeHtml(hr.comment)}</span>` : ''}
  </div>`;
}

function _warnReasonText(codes) {
  if (!codes || !codes.length) return '';
  if (codes.includes('WARN_COMPLETENESS_LOW')) {
    const report = {};
    return '<div class="text-xs text-amber-700 mt-1">能力评分已达标，但元数据完整度未达 90 — 建议补齐 SKILL.md 结构字段后重新提交，可升至 pass</div>';
  }
  if (codes.includes('WARN_SCORE_MIDRANGE')) {
    return '<div class="text-xs text-amber-700 mt-1">综合分在中等档（70–84）— 建议优化技能描述、样例覆盖度后复评</div>';
  }
  if (codes.includes('WARN_NOT_CONFIRMED_FULL')) {
    return '<div class="text-xs text-amber-700 mt-1">未满足 PASS 闸门（需 confirmed + capability_full）— 本次为摸底评估，结论仅供参考</div>';
  }
  return '';
}

function formatScoreDisplay(d) {
  const src = d.score_total_source || (d.report && d.report.score_total_source);
  const codes = (d.report && d.report.reason_codes) || d.reason_codes || [];
  const status = d.status;

  if (status === 'awaiting_confirm') {
    return '<span class="text-amber-700">待作者补全，尚未进入模型评审</span>';
  }
  if (codes.includes('EVAL_PROVIDER_UNAVAILABLE')) {
    return renderProviderErrorPanel(d) || '<span class="text-red-600 font-medium">双模型 API 全部失败</span>';
  }
  if (codes.includes('EVAL_WORKFLOW_TIMEOUT')) {
    const progress = getStageProgress(d);
    const summary = getTimingSummary(d);
    return `<div class="space-y-2">
      <span class="text-red-600 font-medium">评估超时</span>
      ${renderStageProgressList(progress)}
    </div>`;
  }
  if (codes.includes('LOCAL_EXEC_UNAVAILABLE') || codes.includes('LOCAL_EXEC_ALL_CASES_FAILED')) {
    const code = codes.includes('LOCAL_EXEC_UNAVAILABLE') ? 'LOCAL_EXEC_UNAVAILABLE' : 'LOCAL_EXEC_ALL_CASES_FAILED';
    return `<div class="space-y-1">
      <span class="text-red-600 font-medium">本地执行阻断，未出报告</span>
      <div class="text-xs text-red-700">${escapeHtml(REASON_ZH[code] || code)}</div>
    </div>`;
  }
  if (src === 'null_due_to_disagreement') {
    const ps = getProviderSummary(d);
    const bars = ps ? renderProviderSummaryBars(ps, { showR5Headline: true, compact: true }) : '';
    return `<div class="space-y-1"><span class="text-amber-800">模型分歧（R5），综合分暂不可用</span>${bars}</div>`;
  }
  if (d.score_total !== null && d.score_total !== undefined) {
    const ps = getProviderSummary(d);
    const bars = ps && ps.deepseek_score != null
      ? renderProviderSummaryBars(ps, { compact: true })
      : '';
    return `<div class="space-y-1"><strong>${d.score_total}</strong>/100${bars}${_warnReasonText(codes)}</div>`;
  }
  return '<span class="text-gray-400">—</span>';
}

function renderProviderSummaryBars(ps, opts = {}) {
  if (!ps) return '';
  const { showR5Headline = false, compact = false } = opts;
  const providerA = ps.provider_a_label || 'DeepSeek';
  const providerB = ps.provider_b_label || 'Gemini';
  let providerBBanner = '';
  if (ps.gemini_score == null && ps.deepseek_score != null) {
    providerBBanner = `<div class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mb-2">
    ${escapeHtml(providerB)} 本次不可用（API 限流），仅 ${escapeHtml(providerA)} 有效评审，结论仅供参考
  </div>`;
  }
  const ds = ps.deepseek_score != null ? ps.deepseek_score : '—';
  const gm = ps.gemini_score != null ? ps.gemini_score : '—';
  const gap = ps.score_gap != null ? ps.score_gap : '—';
  const gapHi = typeof gap === 'number' && gap >= 15;
  const headline = (showR5Headline || ps.r5_triggered)
    ? '<div class="text-xs text-amber-800 mb-1">模型分歧（R5），综合分暂不可用</div>'
    : '';
  const pad = compact ? 'p-2' : 'p-3';
  return `
    ${providerBBanner}
    ${headline}
    <div class="grid grid-cols-3 gap-2 text-sm mt-1">
      <div class="bg-blue-50 rounded ${pad} text-center border border-blue-100">
        <div class="text-xs text-gray-500">${escapeHtml(providerA)}</div>
        <div class="font-bold font-mono text-blue-900">${ds}</div>
        ${ps.deepseek_bundle_status ? `<div class="text-xs text-gray-500">${escapeHtml(ps.deepseek_bundle_status)}</div>` : ''}
      </div>
      <div class="bg-purple-50 rounded ${pad} text-center border border-purple-100">
        <div class="text-xs text-gray-500">${escapeHtml(providerB)}</div>
        <div class="font-bold font-mono text-purple-900">${gm}</div>
        ${ps.gemini_bundle_status ? `<div class="text-xs text-gray-500">${escapeHtml(ps.gemini_bundle_status)}</div>` : ''}
      </div>
      <div class="bg-gray-50 rounded ${pad} text-center border border-gray-200">
        <div class="text-xs text-gray-500">Δ</div>
        <div class="font-bold font-mono ${gapHi ? 'text-red-600' : 'text-gray-800'}">${gap}</div>
      </div>
    </div>`;
}

function getReportPayload(d) {
  return (d && d.report) ? d.report : (d || {});
}

function renderCompletenessBar(score) {
  if (score == null || score === undefined) return '';
  const pct = Math.max(0, Math.min(100, Number(score)));
  return `
    <div class="mt-2">
      <div class="flex justify-between text-xs text-gray-600 mb-1">
        <span>元数据完整度</span>
        <span class="font-mono">${pct.toFixed(0)}/100</span>
      </div>
      <div class="h-2 bg-gray-100 rounded overflow-hidden">
        <div class="h-full bg-amber-500 rounded" style="width:${pct}%"></div>
      </div>
    </div>`;
}

function renderDiagnosticReportCard(d) {
  const report = getReportPayload(d);
  const gaps = report.gaps || [];
  const actions = report.required_actions || [];
  const completeness = report.completeness_score;
  if (completeness == null && !gaps.length && !actions.length) return '';

  const gapRows = gaps.map(g => `
    <li class="flex items-start gap-2 py-1 border-b border-gray-50 last:border-0">
      ${severityBadge(g.severity)}
      <span class="text-xs text-gray-800"><code class="text-gray-600">${escapeHtml(g.field_path || g.id || '?')}</code>
        — ${escapeHtml(g.message || g.hint || '')}</span>
    </li>`).join('');

  const actionRows = actions.map((a, i) =>
    `<li class="text-xs text-gray-700 py-0.5">${i + 1}. ${escapeHtml(a)}</li>`
  ).join('');

  const status = d.status || report.status;
  const intro = status === 'awaiting_confirm'
    ? '本次仅完成结构检查，尚未进入模型质量评审。请按补全清单操作后重新提交全量评估。'
    : '降级摸底评估已完成，结论仅供参考，不作为上架准入依据。';

  return `
    <div class="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm space-y-2">
      <div class="font-medium text-amber-900">结构诊断报告</div>
      <p class="text-xs text-amber-800">${intro}</p>
      ${renderCompletenessBar(completeness)}
      ${gaps.length ? `<ul class="mt-2">${gapRows}</ul>` : ''}
      ${actions.length ? `
        <div class="mt-2 pt-2 border-t border-amber-100">
          <div class="text-xs font-medium text-amber-900 mb-1">待办（required_actions）</div>
          <ol class="list-decimal list-inside">${actionRows}</ol>
        </div>` : ''}
    </div>`;
}

function formatDimensionTriple(dim) {
  if (!dim) return '—';
  const fmt = (v) => (v != null && v !== undefined) ? v : '—';
  return `指令遵循 ${fmt(dim.instruction_following)} · 输出合规 ${fmt(dim.output_compliance)} · 业务解决 ${fmt(dim.business_resolution)}`;
}

const MAX_FB = 80;
function truncateFb(s) {
  if (!s || s === '—') return '—';
  const safe = escapeHtml(s);
  if (s.length <= MAX_FB) return safe;
  const uid = 'fb' + Math.random().toString(36).slice(2, 7);
  return `${escapeHtml(s.slice(0, MAX_FB))}<span class="text-gray-400">…</span>`
    + `<span id="${uid}-full" class="hidden text-gray-600"> ${safe}</span>`
    + `<button onclick="document.getElementById('${uid}-full').classList.toggle('hidden');this.textContent=this.textContent==='[展开]'?'[收起]':'[展开]'" `
    + `class="text-blue-400 text-xs ml-1 hover:underline">[展开]</button>`;
}

function renderModelVotesFeedback(d, collapsed = true) {
  const report = getReportPayload(d);
  const votes = report.model_votes || [];
  if (!votes.length) return '';
  const ps = getProviderSummary(d) || {};
  const providerA = ps.provider_a_label || 'DeepSeek';
  const providerB = ps.provider_b_label || 'Gemini';

  const byCase = {};
  votes.forEach(v => {
    const cid = v.case_id || '?';
    if (!byCase[cid]) byCase[cid] = { deepseek: null, gemini: null };
    const key = (v.model || '').toLowerCase().includes('gemini') ? 'gemini' : 'deepseek';
    byCase[cid][key] = v;
  });

  const rows = Object.entries(byCase).map(([caseId, pair]) => {
    const ds = pair.deepseek;
    const gm = pair.gemini;
    const dsFb = truncateFb(ds?.feedback);
    const gmFb = truncateFb(gm?.feedback);
    const dsDim = ds && ds.dimension_scores ? formatDimensionTriple(ds.dimension_scores) : '—';
    const gmDim = gm && gm.dimension_scores ? formatDimensionTriple(gm.dimension_scores) : '—';
    return `
      <tr class="border-t border-gray-100">
        <td class="px-2 py-2 font-mono text-xs align-top">${escapeHtml(caseId)}</td>
        <td class="px-2 py-2 text-xs align-top">
          <div class="text-gray-500">${dsDim}</div>
          <div class="text-gray-700 mt-0.5">${dsFb}</div>
        </td>
        <td class="px-2 py-2 text-xs align-top">
          <div class="text-gray-500">${gmDim}</div>
          <div class="text-gray-700 mt-0.5">${gmFb}</div>
        </td>
      </tr>`;
  }).join('');

  return `
    <details class="mt-2"${collapsed ? '' : ' open'}>
      <summary class="cursor-pointer text-xs text-blue-600 font-medium">per-case 评审反馈与三维分 ▼</summary>
      <table class="w-full text-xs mt-2 border border-gray-200 rounded-lg overflow-hidden bg-white">
        <thead class="bg-gray-50 text-gray-500">
          <tr>
            <th class="text-left px-2 py-1">case_id</th>
            <th class="text-left px-2 py-1">${escapeHtml(providerA)}（三维 · 反馈）</th>
            <th class="text-left px-2 py-1">${escapeHtml(providerB)}（三维 · 反馈）</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </details>`;
}

function renderPerCaseDetails(ps, collapsed = true, runId = null, showTrace = false) {
  if (!ps || !ps.per_case || !ps.per_case.length) return '';
  const providerA = ps.provider_a_label || 'DS';
  const providerB = ps.provider_b_label || 'Gemini';
  const rows = ps.per_case.map(row => {
    const hi = row.gap != null && row.gap >= 15;
    const traceCell = showTrace && runId
      ? `<td class="px-2 py-1 text-xs"><a href="/ui/trace.html?run_id=${encodeURIComponent(runId)}#case-${encodeURIComponent(row.case_id)}" target="_blank" rel="noopener" class="text-indigo-700 hover:text-indigo-900 whitespace-nowrap">评分过程 →</a></td>`
      : '';
    const execBadge = row.exec_status === 'incomplete'
      ? `<span class="ml-1 inline-block px-1 rounded bg-red-100 text-red-700 text-[10px] align-middle" title="${escapeHtml(formatExecReadyReason(row.exec_degrade_reason))}">本地执行未完成</span>`
      : '';
    return `
      <tr class="${hi ? 'bg-red-50' : ''}">
        <td class="px-2 py-1 font-mono text-xs">${escapeHtml(row.case_id)}${execBadge}</td>
        <td class="px-2 py-1 text-right">${row.deepseek_score != null ? row.deepseek_score : '—'}</td>
        <td class="px-2 py-1 text-right">${row.gemini_score != null ? row.gemini_score : '—'}</td>
        <td class="px-2 py-1 text-right font-medium ${hi ? 'text-red-600' : ''}">${row.gap != null ? row.gap : '—'}</td>
        <td class="px-2 py-1 text-xs text-gray-600">${escapeHtml(row.ds_suggested_status || '—')} / ${escapeHtml(row.gemini_suggested_status || '—')}</td>
        ${traceCell}
      </tr>`;
  }).join('');
  const traceCol = showTrace
    ? '<th class="text-left px-2 py-1">过程</th>'
    : '';
  return `
    <details class="mt-2"${collapsed ? '' : ' open'}>
      <summary class="cursor-pointer text-xs text-blue-600 font-medium">per-case 分数对照 ▼</summary>
      <table class="w-full text-xs mt-2 border border-gray-200 rounded-lg overflow-hidden bg-white">
        <thead class="bg-gray-50 text-gray-500">
          <tr>
            <th class="text-left px-2 py-1">case_id</th>
            <th class="text-right px-2 py-1">${escapeHtml(providerA)}</th>
            <th class="text-right px-2 py-1">${escapeHtml(providerB)}</th>
            <th class="text-right px-2 py-1">Δ</th>
            <th class="text-left px-2 py-1">建议状态</th>
            ${traceCol}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </details>`;
}

async function pollStatus(runId) {
  try {
    const d = await apiFetch(`/eval/report/${runId}`);
    const body = document.getElementById('run-status-body');
    const terminal = ['completed','failed','awaiting_human_review','awaiting_confirm'].includes(d.status);

    const statusClass = {
      pass:'status-pass', fail:'status-fail', warn:'status-warn',
      awaiting_confirm:'status-awaiting', awaiting_human_review:'status-awaiting',
    }[d.review_status || d.status] || 'status-pending';

    let scoreStr = formatScoreDisplay(d);

    const reasonCodes = (d.report && d.report.reason_codes && d.report.reason_codes.length)
      ? d.report.reason_codes
      : (d.reason_codes || []);
    let reasonHtml = '';
    if (reasonCodes.length) {
      const zhReasons = reasonCodes.map(c => REASON_ZH[c] || c).filter(Boolean);
      reasonHtml = zhReasons.length
        ? `<div class="text-xs text-amber-700 mt-1">${zhReasons.map(r => `• ${escapeHtml(r)}`).join('<br>')}</div>`
        : '';
    }

    let humanHtml = '';
    if (d.human_review_required) {
      humanHtml = `<div class="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
        需要专家复核 — 请切换到右上角【专家】视角，在简卡或完整报告中裁定
      </div>`;
    }

    body.innerHTML = `
      <div class="flex items-center gap-3 flex-wrap">
        <span class="badge ${statusClass}">${d.status}</span>
        ${d.review_status ? `<span class="badge ${statusClass}">${d.review_status}</span>` : ''}
        ${d.human_review_required ? '<span class="badge bg-amber-100 text-amber-700">人工待审</span>' : ''}
        <span class="text-gray-400 text-xs">${runId.slice(0,8)}…</span>
      </div>
      <div class="text-sm">分数：${scoreStr}</div>
      ${terminal ? renderNarrativeCard(d) : ''}
      ${terminal ? renderDisagreementCard(d) : ''}
      ${terminal ? renderRiskLockCard(d) : ''}
      ${reasonHtml}
      ${renderLocalExecCheckRecovery(d)}
      ${renderLevel0Evidence(d)}
      ${humanHtml}
      ${renderProviderErrorPanel(d)}
      ${(terminal && (d.status === 'awaiting_confirm' || (getReportPayload(d).gaps && getReportPayload(d).gaps.length)))
        ? renderDiagnosticReportCard(d) : ''}
      ${terminal && getReportPayload(d).model_votes && getReportPayload(d).model_votes.length
        ? renderModelVotesFeedback(d, true) : ''}
      ${terminal ? renderSkillSummaryCard(d, { collapsed: true }) : ''}
      ${renderLocalAgentBudget(d)}
      ${renderLocalAgentCaseProgress(d)}
      ${terminal ? renderUsageSummary(d) : ''}
      ${terminal ? '<div class="text-xs text-gray-400 mt-1">任务已终结，停止轮询</div>' : '<div class="text-xs text-blue-400 animate-pulse">评估进行中，每 4s 自动刷新…</div>'}
    `;

    if (terminal) {
      stopPolling();
      if (d.status === 'awaiting_confirm') {
        const skillFromReport = (d.report && d.report.skill_id) || document.getElementById('inp-skill-id').value.trim();
        if (skillFromReport) {
          document.getElementById('inp-confirm-skill-id').value = skillFromReport;
          body.innerHTML += `
            <div class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
              待作者补全 — 已填充 Skill ID，正在加载缺口清单…
            </div>`;
          loadGaps(skillFromReport);
        }
      }
    }
  } catch(e) {
    // silent on transient poll errors
  }
}

function severityBadge(severity) {
  const cls = { block: 'bg-red-100 text-red-800', warn: 'bg-amber-100 text-amber-800', info: 'bg-blue-100 text-blue-800' }[severity] || 'bg-gray-100 text-gray-700';
  const label = { block: '阻断', warn: '警告', info: '提示' }[severity] || severity;
  return `<span class="badge ${cls}">${label}</span>`;
}

async function copyTemplate(label, text) {
  try {
    await navigator.clipboard.writeText(text);
    toast(`已复制：${label}`);
  } catch {
    toast('复制失败，请手动选中复制', false);
  }
}

function copyTemplateByKey(key) {
  const labels = { eval_case: 'eval_case 模板', sample_io: 'sample_io 模板', frontmatter: 'frontmatter 片段' };
  const text = _lastGapsSnapshot?.templates?.[key];
  if (text) copyTemplate(labels[key] || key, text);
}

function renderTemplateButtons(templates) {
  if (!templates || !Object.keys(templates).length) return '';
  const items = [
    { key: 'eval_case', label: 'eval_case 模板' },
    { key: 'sample_io', label: 'sample_io 模板' },
    { key: 'frontmatter', label: 'frontmatter 片段' },
  ].filter(t => templates[t.key]);
  if (!items.length) return '';
  return `
    <div class="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
      <div class="text-xs font-semibold text-gray-700 uppercase tracking-wide">可复制模板</div>
      <p class="text-xs text-gray-500">将模板保存至 Bundle 路径对应目录后，再以 confirmed + capability_full 重新发起评估</p>
      ${items.map(t => `
        <div class="border border-gray-200 rounded-lg overflow-hidden bg-white">
          <div class="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-100">
            <span class="text-xs font-medium text-gray-700">${t.label}</span>
            <button type="button" onclick="copyTemplateByKey('${t.key}')"
              class="text-xs text-blue-600 hover:underline">复制</button>
          </div>
          <pre class="text-xs p-3 overflow-x-auto text-gray-600 whitespace-pre-wrap">${escapeHtml(templates[t.key])}</pre>
        </div>
      `).join('')}
    </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Signature：评估流水号牌（仅展示层格式化 run_id，不改数据） ────────────────
function runRefLabel(runId) {
  const compact = String(runId || '').replace(/-/g, '').slice(0, 8).toUpperCase();
  return compact ? `EVAL-${compact}` : '';
}

/** D3: report exec-agent fields are honest — only non-null when a case actually
 * ran via local_agent. Show what ran, or what was requested but didn't run. */
function renderExecAttributionCard(d) {
  const report = getReportPayload(d);
  const agentLabel = report.exec_agent_label;
  const requestedAgentLabel = report.exec_requested_agent_label;
  const skillPath = report.skill_bundle_path || d.skill_bundle_path || '';
  const runtimeId = report.exec_agent_id || _execPreferences?.exec_agent || '';
  const modelId = report.exec_model_id || _execPreferences?.exec_model || 'default';
  const preflightButton = (skillPath && runtimeId)
    ? `<button type="button"
        class="ml-2 inline-flex items-center px-2 py-0.5 border border-amber-300 text-amber-800 bg-white hover:bg-amber-100 text-[11px]"
        onclick="runRuntimePreflightFromDetail('${encodeURIComponent(skillPath)}','${encodeURIComponent(runtimeId)}','${encodeURIComponent(modelId)}')">
        运行环境检查
      </button>`
    : '';
  if (!agentLabel && !requestedAgentLabel) return '';
  if (agentLabel) {
    return `<div class="mt-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2 py-1">
      本地执行：<strong>${escapeHtml(agentLabel)}</strong> / ${escapeHtml(report.exec_model_label || '默认模型')} — 本次已成功执行
      ${preflightButton}
    </div>`;
  }
  return `<div class="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">
    已选择 <strong>${escapeHtml(requestedAgentLabel)}</strong> / ${escapeHtml(report.exec_requested_model_label || '默认模型')}，但本次未成功执行（详见下方失败原因）
    ${preflightButton}
  </div>`;
}

function renderRunRefBar(runId, skillId, statusZh) {
  if (!runId) return '';
  return `
    <div class="run-ref flex items-center flex-wrap gap-x-3 gap-y-1 bg-gray-900 text-white text-xs px-3 py-2">
      <span class="font-semibold tracking-wider">${escapeHtml(runRefLabel(runId))}</span>
      ${skillId ? `<span class="text-gray-400">·</span><span class="text-gray-100">${escapeHtml(skillId)}</span>` : ''}
      ${statusZh ? `<span class="text-gray-400">·</span><span class="text-gray-100">${escapeHtml(statusZh)}</span>` : ''}
      <span class="ml-auto text-gray-400" title="${escapeHtml(String(runId))}">${escapeHtml(String(runId).slice(0, 12))}…</span>
    </div>`;
}

function renderPostConfirmChecklist(blockActions) {
  if (!blockActions || !blockActions.length) return '';
  return `
    <div id="post-confirm-checklist" class="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-900 space-y-2">
      <div class="font-semibold">元数据已确认 — 发起全量评前请核对：</div>
      <ul class="list-disc list-inside text-xs space-y-1">
        ${blockActions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
        <li>结构文件已保存至 Bundle 路径（eval_cases/、sample_io/ 等）</li>
      </ul>
      <p class="text-xs text-amber-700">核对完成后，点击下方「发起评估」（已预填 confirmed + capability_full）</p>
    </div>`;
}

function renderGapsSnapshot(data) {
  const gapsList = document.getElementById('gaps-list');
  const gaps = data.gaps || [];
  const actions = data.required_actions || [];
  const bySeverity = { block: [], warn: [], info: [] };
  gaps.forEach(g => (bySeverity[g.severity] || bySeverity.info).push(g));

  let html = '';
  if (actions.length) {
    html += `
      <div class="p-4 bg-white border border-gray-200 rounded-lg space-y-2">
        <div class="text-sm font-semibold text-gray-900">待办清单</div>
        <ol class="list-decimal list-inside text-sm text-gray-700 space-y-1">
          ${actions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
        </ol>
      </div>`;
  }
  ['block', 'warn', 'info'].forEach(sev => {
    if (!bySeverity[sev].length) return;
    html += `
      <div class="p-4 bg-white border border-gray-200 rounded-lg space-y-2">
        <div class="text-sm font-semibold text-gray-900">${{block:'阻断项',warn:'警告项',info:'提示项'}[sev]}</div>
        ${bySeverity[sev].map(g => `
          <div class="flex items-start gap-2 text-sm">
            ${severityBadge(g.severity)}
            <div>
              <span class="font-mono text-xs text-gray-500">${escapeHtml(g.field_path)}</span>
              <div class="text-gray-700">${escapeHtml(g.message)}</div>
            </div>
          </div>
        `).join('')}
      </div>`;
  });
  const needsTemplates = gaps.some(g => ['eval_cases', 'eval_cases.count', 'sample_io', 'risk_level'].includes(g.field_path));
  if (needsTemplates) {
    html += renderTemplateButtons(data.templates);
  }
  gapsList.innerHTML = html || '<p class="text-sm text-gray-400">暂无缺口记录</p>';
}

function renderSecurityConfirmFields(confirmedFields) {
  const confirmed = confirmedFields || {};
  const pending = SECURITY_FIELDS.filter(f => !confirmed[f]);
  const grid = document.getElementById('confirm-fields-grid');
  if (!pending.length) {
    grid.innerHTML = `<p class="text-sm text-green-700 col-span-2">安全敏感字段均已确认</p>`;
    document.getElementById('confirm-form').classList.remove('hidden');
    return;
  }
  grid.innerHTML = pending.map(f => `
    <div>
      <label class="block text-xs font-medium text-gray-700 mb-1">${SECURITY_LABELS[f]}</label>
      <input type="text" id="field-${f}" placeholder="${SECURITY_PLACEHOLDERS[f]}"
        value="${escapeHtml(confirmed[f] || '')}"
        class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
    </div>
  `).join('');
  document.getElementById('confirm-form').classList.remove('hidden');
}

// ── Load gaps ──────────────────────────────────────────────────────────────────
async function loadGaps(skillIdOverride) {
  const skillId = (skillIdOverride || document.getElementById('inp-confirm-skill-id').value.trim());
  if (!skillId) { toast('请填写 Skill ID', false); return; }
  _confirmSkillId = skillId;

  const gapsList = document.getElementById('gaps-list');
  gapsList.innerHTML = '<p class="text-sm text-gray-400">加载中…</p>';

  try {
    const data = await apiFetch(`/bundle/${encodeURIComponent(skillId)}/gaps`);
    _lastGapsSnapshot = data;
    renderGapsSnapshot(data);
    renderSecurityConfirmFields(data.confirmed_fields);
    toast(`已加载 ${(data.gaps || []).length} 项缺口`);
  } catch (e) {
    gapsList.innerHTML = `<p class="text-sm text-red-500">加载失败：${escapeHtml(String(e.message))}</p>`;
    toast(e.message, false);
  }
}

// ── Submit confirm ─────────────────────────────────────────────────────────────
async function submitConfirm() {
  if (!_confirmSkillId) { toast('请先查询 Gaps', false); return; }
  const operator = document.getElementById('inp-operator').value.trim() || 'author';

  const confirmed_fields = {};
  SECURITY_FIELDS.forEach(f => {
    const el = document.getElementById('field-'+f);
    const val = el?.value.trim();
    if (val) confirmed_fields[f] = val;
  });

  if (Object.keys(confirmed_fields).length === 0) {
    toast('至少填写一个安全字段', false); return;
  }

  const msgEl = document.getElementById('confirm-msg');
  msgEl.textContent = '提交中…';
  try {
    const data = await apiFetch(`/bundle/${_confirmSkillId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ confirmed_fields, operator, confirmed_cases: [] }),
    });
    msgEl.textContent = '';
    toast(`已确认 ${data.confirmed_count} 个字段，可发起 Mode D 全量评审`);
    document.getElementById('inp-skill-id').value = _confirmSkillId;
    document.getElementById('inp-bundle-state').value = 'confirmed';
    document.getElementById('inp-eval-mode').value = 'capability_full';

    const blockActions = (_lastGapsSnapshot?.required_actions || [])
      .filter(a => /eval_cases|sample_io|risk_level|创建|添加|移除/i.test(a));
    const existing = document.getElementById('post-confirm-checklist');
    if (existing) existing.remove();
    document.getElementById('gaps-list').insertAdjacentHTML('beforeend', renderPostConfirmChecklist(blockActions));

    await loadGaps(_confirmSkillId);
  } catch(e) {
    msgEl.textContent = '';
    toast(e.message, false);
  }
}

// ── Expert queue ──────────────────────────────────────────────────────────────
async function loadExpertQueue() {
  const el = document.getElementById('expert-queue');
  el.innerHTML = '<p class="text-sm text-gray-400 text-center py-6">加载中…</p>';
  try {
    const data = await apiFetch('/eval/history?human_review_only=true&limit=30');
    updateReviewBadge(data.total);

    if (!data.runs.length) {
      el.innerHTML = '<div class="text-center py-10 text-gray-400 text-sm">暂无待审核任务</div>';
      return;
    }

    const cards = await Promise.all(data.runs.map(async run => {
      try {
        const detail = await apiFetch(`/eval/report/${run.run_id}`);
        return renderExpertCard(run, detail);
      } catch {
        return renderExpertCard(run, null);
      }
    }));
    el.innerHTML = cards.join('');
  } catch(e) {
    el.innerHTML = `<p class="text-sm text-red-400 text-center py-6">加载失败: ${escapeHtml(String(e.message))}</p>`;
  }
}

function renderExpertReviewActions(runId) {
  return `
    <div class="flex gap-3 items-center pt-1 flex-wrap border-t border-gray-200 mt-3 pt-3">
      <div class="w-full text-xs font-semibold text-amber-900">专家裁定</div>
      <input type="text" id="expert-${runId}" placeholder="专家姓名"
        class="border border-gray-300 rounded-lg px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-blue-300" />
      <button type="button" onclick="submitReview('${runId}', 'approve')"
        class="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
        批准通过
      </button>
      <button type="button" onclick="submitReview('${runId}', 'reject')"
        class="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
        拒绝驳回
      </button>
      <span id="review-msg-${runId}" class="text-xs text-gray-500"></span>
    </div>`;
}

function renderExpertReviewSection(runId, detail) {
  if (!detail || detail.status !== 'awaiting_human_review') return '';
  if (getPerspective() !== 'expert') {
    return `<div class="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
      此评估待专家复核。请切换到右上角【专家】视角后进行裁定。
    </div>`;
  }
  return renderExpertReviewActions(runId);
}

function renderExpertCard(run, detail) {
  const runIdShort = run.run_id.slice(0, 8);
  const ps = detail ? getProviderSummary(detail) : null;
  const r5 = ps && ps.r5_triggered;
  const scoreHtml = detail ? formatScoreDisplay(detail) : (
    run.score_total != null ? `<strong>${run.score_total}</strong>/100` : '<span class="text-gray-400">—</span>'
  );

  const r5Notice = r5 ? `
    <div class="text-xs text-gray-600 bg-red-50 border border-red-100 rounded-lg p-3">
      <span class="font-medium text-red-700">R5 模型分歧</span>：双模型分差或建议状态冲突，需专家裁定综合分。
    </div>` : '';

  const modelBlock = ps
    ? `<div class="space-y-1">
        <div class="text-xs font-medium text-gray-600">双模型包级分数</div>
        ${renderProviderSummaryBars(ps)}
        ${renderPerCaseDetails(ps, true)}
        ${detail ? renderModelVotesFeedback(detail, true) : ''}
      </div>`
    : (detail ? renderModelVotesFeedback(detail, true) : '<p class="text-xs text-gray-400">加载 report 后可查看 per-case 对照</p>');

  return `
  <div class="border border-gray-200 rounded-xl p-5 bg-gray-50 space-y-3" id="card-${run.run_id}">
    <div class="flex items-start justify-between flex-wrap gap-2">
      <div>
        <div class="font-semibold text-gray-900">${escapeHtml(run.skill_id)}</div>
        <div class="run-ref text-xs text-gray-400 mt-0.5" title="${escapeHtml(run.run_id)}">${escapeHtml(runRefLabel(run.run_id))} · ${escapeHtml(run.status)}</div>
      </div>
      <div class="flex gap-2 flex-wrap">
        ${renderBadge(run.review_status)}
        <span class="badge bg-amber-100 text-amber-700">人工待审</span>
      </div>
    </div>

    <div class="text-sm bg-white rounded-lg p-3 border border-gray-200">
      <div class="text-xs text-gray-400 mb-1">综合得分</div>
      ${scoreHtml}
    </div>

    ${r5Notice}
    ${detail ? renderNarrativeCard(detail) : ''}
    ${detail ? renderDisagreementCard(detail) : ''}
    ${detail ? renderRiskLockCard(detail) : ''}
    ${modelBlock}
    ${detail ? renderSkillSummaryCard(detail, { collapsed: true }) : ''}

    ${renderExpertReviewActions(run.run_id)}
  </div>`;
}

function renderExpertVerdictCard(runId, detail, action, operator, reviewStatus) {
  const ps = getProviderSummary(detail);
  const hr = (detail.report && detail.report.human_review) || {};
  const actionLabel = action === 'approve' ? '批准通过' : '驳回';
  return `
    <div class="space-y-3 py-1">
      <div class="flex items-center gap-3 flex-wrap">
        ${renderBadge(reviewStatus)}
        <span class="badge bg-indigo-100 text-indigo-800">专家裁定</span>
        <span class="text-sm text-gray-700">由 <strong>${escapeHtml(operator)}</strong> ${actionLabel}</span>
        <span class="run-ref text-xs text-gray-400 ml-auto" title="${escapeHtml(runId)}">${escapeHtml(runRefLabel(runId))}</span>
      </div>
      ${hr.comment ? `<p class="text-xs text-gray-500">${escapeHtml(hr.comment)}</p>` : ''}
      ${ps ? renderProviderSummaryBars(ps) : ''}
      ${ps ? renderPerCaseDetails(ps, false) : ''}
      ${renderModelVotesFeedback(detail, false)}
      <p class="text-xs text-gray-400">per-case 快照已保留，供审计对照</p>
    </div>`;
}

async function submitReview(runId, action) {
  const operator = document.getElementById(`expert-${runId}`)?.value.trim() || 'expert';
  const msgEl = document.getElementById(`review-msg-${runId}`);
  if (msgEl) msgEl.textContent = '提交中…';
  try {
    const data = await apiFetch(`/eval/review/${runId}`, {
      method: 'POST',
      body: JSON.stringify({ action, operator, comment: `Manual ${action} by ${operator}` }),
    });
    toast(`${action === 'approve' ? '已批准' : '已驳回'} — review_status: ${data.review_status}`);
    const card = document.getElementById(`card-${runId}`);
    if (card) {
      try {
        const detail = await apiFetch(`/eval/report/${runId}`);
        card.innerHTML = renderExpertVerdictCard(runId, detail, action, operator, data.review_status);
      } catch {
        card.innerHTML = `
          <div class="flex items-center gap-3 py-2">
            ${renderBadge(data.review_status)}
            <span class="text-sm text-gray-600">由 <strong>${escapeHtml(operator)}</strong> ${action === 'approve' ? '批准' : '驳回'}</span>
          </div>`;
      }
    }
    if (document.getElementById('expert-queue')) loadExpertQueue();
    if (_activeConversationId) {
      _lastRenderedMessageKeys = [];
      pollConversation();
    }
    const modal = document.getElementById('detail-modal');
    if (modal && !modal.classList.contains('hidden')) {
      await openRunDetail(runId, { origin: 'chat' });
    }
    if (!document.getElementById('panel-history')?.classList.contains('hidden')) {
      loadHistory();
    }
  } catch(e) {
    if (msgEl) msgEl.textContent = '';
    toast(e.message, false);
  }
}

// ── History ───────────────────────────────────────────────────────────────────
function conversationMessagePreview(m) {
  const mtype = m.message_type || 'text';
  const typeLabels = {
    rich_report: '评估简卡',
    local_execution_check: '本地执行环境检查',
    readiness_result: '评估条件检查',
    assessment_gate_result: '评估条件检查',
    propagation_plan: '评估材料补充',
    propagation_summary: '补题完成',
    draft_preview: '修改草案',
  };
  if (typeLabels[mtype]) return `[${typeLabels[mtype]}]`;
  const text = normalizeMessageText(m).trim();
  return text.length > 48 ? `${text.slice(0, 48)}…` : text;
}

function renderHistoryFilterChips() {
  const keys = ['all', 'sample', 'local', 'spotcheck'];
  keys.forEach((k) => {
    const el = document.getElementById(`history-chip-${k}`);
    if (!el) return;
    if (_historyFilterKey === k) {
      el.className = 'tab-active py-1.5 border border-transparent';
    } else {
      el.className = 'tab-inactive py-1.5 border border-gray-300';
    }
  });
}

function setHistoryFilter(nextKey) {
  _historyFilterKey = nextKey || 'all';
  renderHistoryFilterChips();
  loadHistory();
}

function renderConversationSummary(convData) {
  const msgs = convData.messages || [];
  const preview = msgs.slice(-3).map(m => {
    const role = normalizeMessageRole(m);
    const label = role === 'user' ? '你' : (role === 'system' ? '系统' : '助手');
    const body = conversationMessagePreview(m) || '—';
    return `<div class="text-xs text-gray-600"><span class="text-gray-400">${label}:</span> ${escapeHtml(body)}</div>`;
  }).join('');
  const total = convData.message_count || msgs.length;
  return `
    <div class="border-t border-gray-100 pt-3 space-y-2">
      <div class="text-xs font-medium text-gray-700">最近对话（共 ${total} 条，仅显示末尾 3 条）</div>
      <div class="space-y-1 max-h-24 overflow-y-auto bg-gray-50 rounded-lg p-2">${preview || '<p class="text-xs text-gray-400">暂无消息</p>'}</div>
    </div>`;
}

async function openConversationFromHistory(convId, runId) {
  closeRunDetail();
  switchTab('author');
  await selectSession(convId);
  if (runId) _activeRunId = runId;
}

async function loadHistory() {
  const humanOnly = document.getElementById('filter-human')?.checked;
  const el = document.getElementById('history-table');
  renderHistoryFilterChips();
  el.innerHTML = '<p class="text-sm text-gray-400 text-center py-10">加载中…</p>';
  try {
    const params = new URLSearchParams();
    params.set('limit', '50');
    if (humanOnly) params.set('human_review_only', 'true');
    if (_historyFilterKey === 'sample') params.set('execution_source', 'sample_io');
    if (_historyFilterKey === 'local') params.set('execution_source', 'local_agent');
    if (_historyFilterKey === 'spotcheck') params.set('spot_check_only', 'true');
    const data = await apiFetch(`/eval/history?${params.toString()}`);
    const runs = (data.runs || []).filter(run => run.evaluation_mode !== 'degraded');
    if (!runs.length) {
      el.innerHTML = '<p class="text-sm text-gray-400 text-center py-10">暂无历史记录</p>';
      return;
    }
    el.innerHTML = `
      <table class="w-full text-sm">
        <thead>
          <tr class="text-xs text-gray-500 bg-gray-50 border-y border-gray-200 tracking-wide">
            <th class="text-left px-4 py-3 font-medium">对话</th>
            <th class="text-left px-4 py-3 font-medium">Skill ID</th>
            <th class="text-left px-4 py-3 font-medium">Run ID</th>
            <th class="text-left px-4 py-3 font-medium">状态</th>
            <th class="text-left px-4 py-3 font-medium">评审结果</th>
            <th class="text-right px-4 py-3 font-medium">得分</th>
            <th class="text-right px-4 py-3 font-medium">耗时</th>
            <th class="text-left px-4 py-3 font-medium">标记</th>
          </tr>
        </thead>
        <tbody>
          ${runs.map(run => `
            <tr class="border-b border-gray-50 hover:bg-gray-50 cursor-pointer" onclick="openRunDetail('${run.run_id}')">
              <td class="px-4 py-3" onclick="event.stopPropagation()">
                ${run.conversation_id
                  ? `<div class="text-xs text-gray-500 max-w-[160px] truncate" title="${escapeHtml(run.last_message_preview || '')}">${escapeHtml((run.last_message_preview || '—').slice(0, 40))}</div>
                     <div class="text-xs text-gray-400">${run.lui_message_count || 0} 条</div>
                     <button type="button" onclick="openConversationFromHistory('${run.conversation_id}', '${run.run_id}')"
                       class="text-xs text-blue-600 hover:underline mt-1">打开完整对话</button>`
                  : '<span class="text-xs text-gray-400">—</span>'}
              </td>
              <td class="px-4 py-3 font-medium text-gray-900">${run.skill_id}</td>
              <td class="px-4 py-3 text-xs">
                <span class="run-ref text-gray-700">${escapeHtml(runRefLabel(run.run_id))}</span>
                <div class="run-ref text-[10px] text-gray-400" title="${escapeHtml(run.run_id)}">${run.run_id.slice(0,12)}…</div>
              </td>
              <td class="px-4 py-3"><span class="badge ${statusClass(run.status)}">${escapeHtml(statusLabel(run.status))}</span></td>
              <td class="px-4 py-3">${run.review_status ? `<span class="badge ${statusClass(run.review_status)}">${escapeHtml(statusLabel(run.review_status))}</span>` : '—'}</td>
              <td class="px-4 py-3 text-right text-sm">${formatScoreCompact(run)}</td>
              <td class="px-4 py-3 text-right text-xs">${formatTimingSummaryCell(run.timing_summary)}</td>
              <td class="px-4 py-3">${run.human_review_required ? '<span class="badge bg-amber-100 text-amber-700">待审</span>' : ''}${(run.reason_codes || []).includes('EVAL_WORKFLOW_TIMEOUT') ? '<span class="badge bg-red-100 text-red-700 ml-1">超时</span>' : ''}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <div class="text-xs text-gray-400 px-4 py-3 border-t border-gray-100">${runs.length} 条记录</div>
    `;
  } catch(e) {
    el.innerHTML = `<p class="text-sm text-red-400 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

async function openRunDetail(runId, opts = {}) {
  try {
    const d = await apiFetch(`/eval/report/${runId}`);
    const ps = getProviderSummary(d);
    const codes = (d.report && d.report.reason_codes) || d.reason_codes || [];
    const progress = getStageProgress(d);
    const convId = d.conversation_id;
    const showTrace = Boolean(
      d.has_judge_trace
      && (d.evaluation_mode === 'capability_full'
        || (d.report && d.report.evaluation_mode === 'capability_full')),
    );
    let convBlock = '';
    if (convId && opts.origin !== 'chat') {
      try {
        const convData = await apiFetch(`/eval/history/${runId}/conversation`);
        convBlock = renderConversationSummary(convData)
          + `<button type="button" onclick="openConversationFromHistory('${convId}', '${runId}')"
              class="mt-2 text-sm font-medium text-blue-700 hover:text-blue-900 underline">
              打开完整对话 →
            </button>`;
      } catch (_) {
        convBlock = `<button type="button" onclick="openConversationFromHistory('${convId}', '${runId}')"
            class="mt-2 text-sm font-medium text-blue-700 hover:text-blue-900 underline">
            打开完整对话 →
          </button>`;
      }
    }
    const body = document.getElementById('detail-modal-body');
    const detailSkillId = (d.report && d.report.skill_id) || d.skill_id || '';
    const detailStatusZh = statusLabel(d.review_status || d.status);
    body.innerHTML = `
      ${renderRunRefBar(runId, detailSkillId, detailStatusZh)}
      <div class="space-y-2 text-xs font-mono text-gray-500 border border-gray-200 border-t-0 px-3 py-2">
        <div>status: ${escapeHtml(d.status)} · review: ${escapeHtml(d.review_status || '—')}</div>
        ${codes.length ? `<div class="text-xs text-amber-700 mt-1">${codes.map(c => REASON_ZH[c] || c).map(r => `• ${escapeHtml(r)}`).join('<br>')}</div>` : ''}
      </div>
      <div class="text-sm border-t border-gray-100 pt-3">${formatScoreDisplay(d)}</div>
      ${renderExecAttributionCard(d)}
      ${convBlock}
      ${renderDiagnosticReportCard(d)}
      ${progress.length ? `<div class="border-t border-gray-100 pt-3">${renderStageProgressList(progress)}</div>` : ''}
      ${renderLocalAgentBudget(d)}
      ${renderLocalAgentCaseProgress(d)}
      ${ps ? `<div class="border-t border-gray-100 pt-3">${renderProviderSummaryBars(ps)}${renderPerCaseDetails(ps, true, runId, showTrace)}</div>` : ''}
      ${renderModelVotesFeedback(d, true)}
      ${renderUsageSummary(d)}
      ${renderNarrativeCard(d)}
      ${renderDisagreementCard(d)}
      ${renderRiskLockCard(d)}
      ${renderHumanReviewVerdict(d)}
      ${renderSkillSummaryCard(d, { collapsed: false })}
      ${renderExpertReviewSection(runId, d)}
    `;
    document.getElementById('detail-modal').classList.remove('hidden');
  } catch(e) {
    toast(e.message, false);
  }
}

function closeRunDetail() {
  document.getElementById('detail-modal').classList.add('hidden');
}

// ── Badge helpers ─────────────────────────────────────────────────────────────
function renderBadge(s) {
  return `<span class="badge ${statusClass(s)}">${s || '—'}</span>`;
}

function statusClass(s) {
  return { pass:'status-pass', fail:'status-fail', warn:'status-warn',
           awaiting_confirm:'status-awaiting', awaiting_human_review:'status-awaiting',
           completed:'status-pass', failed:'status-fail' }[s] || 'status-pending';
}

function updateReviewBadge(count) {
  const badge = document.getElementById('review-badge');
  const dot = document.getElementById('expert-pending-dot');
  if (badge) {
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }
  if (dot) dot.classList.toggle('hidden', !(count > 0));
}

// ── Init ──────────────────────────────────────────────────────────────────────
checkHealth();
setInterval(checkHealth, 30000);
setPerspective(getPerspective());
const _demoOnInit = localStorage.getItem(DEMO_MODE_KEY) === 'true';
document.getElementById('demo-path-wrap')?.classList.toggle('hidden', !_demoOnInit);
loadSessionList({ force: true });
renderHistoryFilterChips();
(async () => {
  await initExecBridge();
  const stored = readStoredConversationId();
  if (stored) await resumeConversation(stored);
})();

document.getElementById('chat-input')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
});

// Preload expert queue badge on load
apiFetch('/eval/history?human_review_only=true&limit=1')
  .then(d => updateReviewBadge(d.total))
  .catch(() => {});
