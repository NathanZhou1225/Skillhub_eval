---
risk_level: high
name: stock-radar
description: A 股个股诊断 IM 风格 skill（V5.1 + Phase 2a–2e）。当投顾在 IM 对话中遇到 A 股个股代码或股票名称的研判需求时调用。Agent 只写结构化 diagnosis_bundle.json（含次要维 html_expanded），然后一键调用 run_diagnosis_pipeline.sh 交付 IM + HTML；禁止 Agent 写 HTML/CSS/JS 或手写 IM 骨架/表格摘要。产出含总结前瞻 / 今天告诉客户什么 / 6 维 / J1-J5 / 免责；IM 500–750 字优先。不用于宏观策略、多股对比、非 A 股标的。
category: fin-research/quant-signal
---

# stock-radar · A 股个股诊断 IM 风格 skill（V5.1）

## 适用场景

A 股 IM 对话中包含个股代码或名称的研判类问题：

- 个股看法：「诊断一下 600519」「看下贵州茅台」
- 持仓决策：「客户问 000858 能不能加仓」「浮盈 35% 要不要止盈」
- 异动归因：「这只票今天异动什么原因」
- 组合检视：「C001 持仓里的 600519 现状如何」
- 冷门股认知：「这只票是做什么的、为什么这么冷」

不适用：宏观 / 行业策略整体研判；多股横向对比（走独立的 stock-compare）；纯行情查询（用行情软件即可）；港美股、基金、债券等非 A 股；客户直接消费的报告（本输出为投顾参考，需投顾翻译给客户）。

## 全流程

诊断分 **前半段（Agent 研判）** 与 **后半段（Pipeline 确定性交付）**，二者物理隔离：

| 段 | 负责方 | 步骤 |
|----|--------|------|
| **前半段** | Agent | Step 1 取数 → Step 2–4 研判 → Step 5 写 bundle |
| **后半段** | `run_diagnosis_pipeline.sh` | validate → assemble → format IM → render HTML |

**禁止** Agent 手动逐步调用 `validate_bundle.py` / `assemble_bundle.py` / `format_im_from_bundle.py` / `render_html.py`（见 Step 6）。

### Step 1 · 取数（行情 + 资讯 + 板块 + 市场）

按以下顺序拉数据，单源失败按 `references/data-sources.md` 的降级规则处理。

**1.1 日线 K 线（统计 + 技术枚举）**
- 工具：`python3 scripts/akshare_fetch.py <code>`（akshare 腾讯源 `stock_zh_a_hist_tx`；脚本不带 shebang，必须以 `python3` 调用）
- 输出：`/tmp/stock-radar/<code>.json` 含 `summary.last_close`、涨跌幅、`summary.technical_snapshot`（均线结构/趋势/突破枚举）
- **Phase 2b**：同次调用另写 `/tmp/stock-radar/<code>.html-data.json`（fetch_html 契约，供 HTML 层；LLM **不可见**）
- **持久化隔离**：`/tmp/stock-radar/` 仅为 fetch 中间态；**禁止**将 agent bundle 写入此目录
- **禁止**依赖 JSON 中的 OHLC 时间序列（V5 已不输出 `kline_recent_60`）；**禁止**从 K 线倒推支撑/阻力写入正文
- 单位坑：腾讯源 `amount` 字段单位是"手"（不是成交额万元），需用 `成交量 × 收盘价` 自行换算成交额

**1.2 实时盘中报价（盘中诊断拉，收盘后可跳过）**
- 工具：`curl "https://qt.gtimg.cn/q=<sz|sh><code>"`
- 字段：现价 / 昨收 / 今开 / 当日高低 / 成交量手数 / 涨跌幅 / 时间戳（**仅用于标题行**）
- 字段详表见 `references/data-sources.md`

**1.3 个股资讯 / 业绩 / 题材**
- 工具：WebSearch
- 查询模板：`<股票名> <代码> <年月> 业绩 题材 最新`
- 抓：最新季报增速、近期重大公告、题材归属、近期催化事件

**1.4 所属板块表现 + 同业可比**
- 工具：WebSearch
- 查询模板：`<板块名> <年月> 表现 同业 涨跌`
- 抓：板块 YTD / 近 N 日累计涨跌、同业龙头 Q1 业绩 / YTD 涨幅
- 这是 5 状态判定中"板块共振态"的核心依据

**1.5 市场环境 / 大盘风格**
- 工具：WebSearch
- 查询模板：`A股 <年月> 上证指数 主线 风格 切换`
- 抓：上证当前点位、主线方向、是否在高低切换、当日盘面强弱板块对比

**1.6 政策催化（按需）**
- 工具：WebSearch
- 抓：政治局会议 / 工信部 / 国务院专项规划等顶层政策对该题材的影响

### Step 2 · 5 状态前置判定 + 注意力路由

J1-J5 之前先识别个股当前所处的"市场状态"，并**立即查注意力矩阵**确定 1–2 个核心维度。

5 状态速查：

| 状态 | 一句话特征 |
|------|----------|
| 个股异动态 | 单日大涨 / 大跌或停牌前后异动 |
| 板块共振态 | 与板块同涨同跌强相关 |
| 活跃热点态 | 持续高换手、概念榜前列 |
| 阶段切换态 | 突破 / 跌破结构 + 量能突变 |
| 平静无驱动态 | 低换手 + 小区间震荡 + 无事件 |

**输出落点**：
- 【总结前瞻】：**80–110 字融合短文**（状态 + 昨日➔今日演化 + 驱动 + **风险加剧/缓和/持平**）；**无三档评级**；禁止「升级/降级」
- **同时**写 `summary_hook_display`：**同段驱动/演化，省略核心风险句**（30–110 字；供 HTML；`format_im` 不读）
- 查表标记核心维 / 次要维 → 进入 Step 3

详细判定阈值、复合状态、演化强制、注意力矩阵 → `references/state-judgment.md`

### Step 3 · 6 维分析（核心满写 + 次要空标签）

**物理顺序不可变**：基本面 → 技术面 → 资金面 → 消息面 → 概念 / 产业链 → 市场环境。

1. 按 Step 2 注意力矩阵，仅对 **1–2 个核心维** 拉事实并写满 `结论：` `数据：` `解读：`（数据竖排 `·`）
2. 对其余 **4 个次要维** 使用模板**逐字固定**三行废话（见 `templates/im-diagnosis.md`「次要维度 · 固定话术」）；解读禁止加戏
3. **同时**在每个 `role=secondary` 维写入 **`html_expanded`**（结论 + 1–5 条数据 + 解读），供 HTML 证据层展开；IM 字段仍固定三行，`format_im` 不读 `html_expanded`（Phase 2e 双轨叙事）
4. **【技术面】**：仅用 `technical_snapshot` + 动能词（趋势转强、突破中长期压制、跌破前低区间等）；**禁止** MA 具体价格、支撑位、阻力位；`html_expanded` 中技术面同样黑盒化
5. 数据不可得时标「暂缺」，**不省略章节**；`fund_flow_error` / `info_error` 按模板容灾

### Step 4 · J1-J5 五大判断（单行）

J1-J5 是**推理层**，6 维是**事实层** — 禁止在 J 行复述 6 维数字。

| 编号 | 功能名 | V5 输出 |
|------|--------|---------|
| J1 | 主驱动 · 是什么在推这只票 | **单行** ≤40 字；可含 `详见上方【XX】【YY】` |
| J2 | 还能涨多久 | **单行**：窗口（如 3–7 个交易日 / 1–3 月） |
| J3 | 现在处于哪个阶段 | **单行** + `（共识深化\|共识退潮\|阶段持平 — 与昨日相比）`；禁止「升级/降级」 |
| J4 | 是跟板块还是独立走 | **单行** |
| J5 | 主要风险点 | **单行** 1–2 条最高风险；**禁止**七类逐项 |

**禁止** J 内使用 `结论：`、`反例排除：`、`关键节奏：` 等子标签。

### Step 5 · 写入 diagnosis bundle（唯一真源 · Structured Output）

**禁止** Agent 直接撰写 IM 纯文本或任何 HTML/CSS/JS（见 **D0 视图层禁令**）。

按 `schemas/diagnosis_bundle.schema.json` 一次性输出完整 JSON，落盘至：

- 默认：`workspace-stock-diagnose/output/diagnosis/<code>/<timestamp>.bundle.json`
- 可覆盖：环境变量 `STOCK_RADAR_OUTPUT_DIR`

**Agent 只填**（不得包含 `fetch` / `fetch_html`）：

| 节点 | 内容 |
|------|------|
| `meta` | 代码、名称、诊断时间、盘中/收盘、现价、涨跌幅、标题上下文；**可选** `benchmark_sector: { name, index_code }`（见下） |
| `judgment` | 5 状态、`core_dimensions` / `secondary_dimensions`（须与矩阵一致）、`technical_evolution` |
| `narrative` | `summary_hook`、`summary_hook_display`（HTML 专用）、`client_brief`、6 维 + 次要维 `html_expanded` |
| `judgments_j` | J1–J5 + `j3_consensus` 枚举（**IM 唯一 J 源**） |
| `judgments_j_expanded` | **HTML 专用**（schema 1.2.0+）：J1–J4 `headline/conclusion/…`；J5 `risks[]` 八类逐项；`format_im` **不读** |
| `provenance` | `data_notes`、`fetch_errors`（若有）、固定 `disclaimer` 常量 |

字段语义、次要维 `role` 约束、字数规约 → 仍遵循 `templates/im-diagnosis.md` 与 Step 3–4。范本 bundle → `fixtures/*.bundle.json`。

**`meta.benchmark_sector`（HTML 板块 K 线 overlay + 右图 5 日板块资金）**：

| 字段 | 要求 |
|------|------|
| `name` | **东财可命中的概念/行业全名**（如「人形机器人」「机器人概念」）；**禁止**单字或 ≤3 字裸名（如「机器人」）—— 易未匹配或拖慢 probe |
| `index_code` | 有则必写（如 `BKxxxx`）；无则留 `null`，由 fetch 层 alias + cache 解析 |

Step 1 拉数 CLI 第 4 参 `sector_name` 与 bundle 内 `benchmark_sector.name` **保持一致**。

### Step 6 · 一键交付（Pipeline · Phase 2d / 2d.1）

Agent 写完 bundle 后，**只调用**编排脚本（**禁止**分步 exec 各 Python 脚本）：

```bash
cd workspace-stock-diagnose/skills/stock-radar
bash scripts/run_diagnosis_pipeline.sh output/diagnosis/<code>/<timestamp>.bundle.json
```

**Windows**：须用 **Git Bash** 或 **WSL** 执行上述 bash 脚本（`.ps1` wrapper 尚未提供，见 backlog）。

可选：`--fetch-dir /tmp/stock-radar`（默认即此目录，与 Step 1 输出对齐）

**脚本行为**（Agent 无需手动干预）：

1. `validate_bundle.py` — 失败则 **exit 1**，stderr 输出具体 Schema/矩阵/叙事错误；Agent 修正 bundle 后重跑
2. `assemble_bundle.py` — 注入 `/tmp/stock-radar/<code>.json` 与 `html-data.json`
3. `format_im_from_bundle.py` — 生成 IM 纯文本
4. 写入 `output/diagnosis/<code>/latest.im.txt`（**IM 真源文件**，防 stdout 截断）
5. `render_html.py` — 输出 `output/diagnosis/<code>/latest.html`；**失败不 exit 1**，仍交付 IM + bundle 路径

**stdout 交付格式**（路径参考；IM 正文以文件为准）：

```
===== IM 摘要内容 =====
(IM 纯文本…)
=======================
[交付物路径]
IM file: …/latest.im.txt
Bundle (agent): …
Bundle (assembled): …
HTML: …/latest.html
```

若 HTML 行含 `(未生成) [HTML 渲染失败，仅交付文本]`：**禁止** Agent 手写 HTML 补救；只交付 IM + bundle 路径 + 失败声明。

### IM 交付硬规（Phase 2d.1 · 强制）

向用户回复时：

1. **`read` `latest.im.txt`（优先）或 copy stdout 的 `===== IM 摘要内容 =====` 块**，**原样全量**粘贴给用户 — 不得改写、不得缩写
2. **禁止**以任何形态替代 pipeline IM，包括但不限于：
   - markdown 表格（`| 维度 | 信号 |`）
   - 自创「关键信号变化」「诊断摘要」「一页纸总结」
   - bullet 精简版、口语复述版
3. 路径信息可一行带过；**IM 正文不可省略**
4. **去工程化**：validate/exec 日志仅 stderr/内部；飞书用户只见 IM 全文 + 一行 HTML 路径（或渲染失败一句）

### 端到端交付清单（Step 6 完成后）

Agent 向投顾交付时必须包含：

1. **IM 摘要正文**（`read` `output/diagnosis/<code>/latest.im.txt` 并**原样全量**发送；或 paste stdout IM 块）
2. **Bundle 路径**（agent + assembled，可一行）
3. **HTML 路径**（`latest.html`）或渲染失败声明（一行）

**禁止**用表格摘要、bullet 精简版或口语复述替代第 1 项。

### Step 7 · 交付前自检（V5.1）

对 **bundle 内容**（`validate_bundle` 已覆盖大部分）及 **format 输出**做最终确认：

1. **硬锚点齐全**：五大模块标题、6 维 `结论/数据/解读`、J1–J5 标头、`———`、免责
2. **技术面黑盒化**：除标题行外，全文无具体价格、支撑位、阻力位、MA 价位；【技术面】无 OHLC 倒推
3. **接口 error 降级**：若 JSON 有 `fund_flow_error` / `info_error`，对应维已「暂缺」且【数据备注】有声明
4. **合规底线**：全文不含买卖方向词；术语符合 `references/term-glossary.md`
5. **演化词表**：总结风险用「风险加剧/缓和/持平」；J3 用「共识深化/共识退潮/阶段持平 — 与昨日相比」；全文无「升级」「降级」
6. **次要维固定废话**：4 个次要维（技术面临界演化除外）逐字为「非当前主导 / 无核心异动 / 不作交易参考」
7. **叙事切割**：总结无操作建议；客户段无驱动复述；核心维解读各 1 句；总结与客户段无 ≥4 字连续相同短语
8. **跨段去重**：主题词（分歧兑现、情绪退潮等）全文各 ≤2 次；J1 含 `详见上方【核心维】`
9. **演化一致性**：总结含 ➔ 时，数据备注不得写「暂无法对比昨日」或「首次诊断无昨日对比基准」
10. **IM 真源一致**：用户可见正文 === `latest.im.txt`（或 stdout IM 块）全文，非 Agent 自写摘要

任一项不过则回到 Step 5 修正 bundle，不带瑕疵版交付。

## D0 · 视图层禁令（Phase 2a 起强制）

1. **禁止** Agent `write`/`edit` 任何 `.html`、`.css`、含 ECharts/Chart 的 JS 文件
2. **禁止** Agent 直接输出 IM 骨架排版（必须由 `format_im_from_bundle.py` 生成）；**禁止**以表格/摘要/口语复述替代 pipeline IM（含 `latest.im.txt`）
3. **禁止** Agent 在 bundle 中填写 `fetch` / `fetch_html`（由 `assemble_bundle.py` 注入）
4. **禁止** Agent 在 bundle 中填写 UI 字段（如 `radar_weights`、图表 config）
5. HTML 渲染（Phase 2c/2d）仅允许 `run_diagnosis_pipeline.sh` → `render_html.py` + 锁死模板；render 失败时只交付 IM + bundle 路径，**禁止** LLM 补救 HTML
6. **禁止** Agent 分步调用 pipeline 内的 Python 脚本；研判与渲染彻底解耦

## 合规约束（四条底线）

1. **不给买卖方向**：禁止任何方向性动作词与点位预测；允许「短线追涨风险高」等风险**定性**（不写三档评级块）。禁止词与动能替换见 `references/term-glossary.md`
2. **强制判断依据**：J1 单行须能回链到核心维（`详见上方【XX】`）
3. **风险机会并列**：J5 单行须点出 1–2 条最高风险
4. **底部免责声明**：每份输出底部必须照抄附上：

```
以上分析基于公开数据，仅供投顾内部参考，不构成投资建议；本文不涉及具体买卖点位与目标价；最终投资决策需结合客户风险承受能力与投顾独立判断。
```

## 术语翻译

任何专业术语按 `references/term-glossary.md` 处理（含点位黑名单 → 动能词映射）。

## 失败兜底

兜底三原则：

1. **降级有迹**：接口失败时按降级路径走，不卡死、不空转
2. **不编造**：无数据时标"暂缺"继续，禁止凭印象补全催化 / 业绩
3. **失败要声明**：所有接口失败项必须在 IM 输出"数据备注"段显式列出，避免读者误以为数据完整

具体故障策略、降级路径、输出层声明清单详见 `references/data-sources.md`。

## 依赖准备

首次使用前确认 Python 环境已装好 `akshare`：

```bash
python3 -c "import akshare; print(akshare.__version__)"
# 若提示 ModuleNotFoundError，执行：
pip install "akshare>=1.17"
```

依赖清单（脚本运行时实际用到的）：

- Python 3.10+
- akshare ≥ 1.17（行情 / 资金流 / 个股资料三类接口）
- jsonschema ≥ 4.17（bundle 校验）
- Jinja2 ≥ 3.0（HTML render）
- pandas（akshare 间接依赖，通常 pip install akshare 时自动装好）

调用约定：脚本不带 shebang，必须以 `python3 scripts/akshare_fetch.py <code>` 调用，不要直接 `./scripts/akshare_fetch.py`。详见 `references/data-sources.md`。

## 详细参考

- `templates/im-diagnosis.md` — V5 IM 文本骨架 + 空标签 + 字数规约
- `references/state-judgment.md` — 5 状态 + 注意力矩阵 + 演化规则
- `references/term-glossary.md` — 术语白名单 + 点位黑名单
- `references/data-sources.md` — 数据源映射 + 字段单位坑 + 接口降级路径
- `examples/300276-三丰智能.v5.txt` — 个股异动态（V5 验收范本）
- `examples/300308-中际旭创.v5.txt` — 活跃热点态 + 高位调整（V5）
- `examples/600519-贵州茅台.v5.txt` — 平静无驱动态 → 临界（V5）
- `examples/*-*.v3.txt` — 历史长稿对照（勿照抄篇幅）
- `schemas/diagnosis_bundle.schema.json` — Phase 2a/2e/2h/4 bundle 契约（schema 1.2.1；`summary_hook_display` + `judgments_j_expanded`）
- `fixtures/*.bundle.json` — 三份验收 mock（对应 v5 范本）
- `scripts/akshare_fetch.py` — 行情取数（LLM：`/tmp/stock-radar/<code>.json`；HTML：`/<code>.html-data.json`）
- `scripts/validate_fetch_html.py` — fetch_html Schema + 三态校验（`--test` 跑 fixture）
- `schemas/fetch_html.schema.json` — HTML 数据层契约
- `scripts/validate_bundle.py` — Schema + 矩阵 + 叙事规则校验
- `scripts/assemble_bundle.py` — merge fetch → 持久化 assembled bundle
- `scripts/format_im_from_bundle.py` — IM 确定性生成（唯一真源）
- `scripts/run_diagnosis_pipeline.sh` — **唯一**后半段交付入口（validate → assemble → IM → HTML）
- `scripts/render_html.py` — HTML 证据层（由 pipeline 内部调用；Agent 禁止直接调用）
- `templates/radar_view.html.j2` — HTML 视图锁死模板（Agent 禁止 edit）
