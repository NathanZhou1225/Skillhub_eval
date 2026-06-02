# 数据源映射 + 字段单位坑 + 接口降级路径

本文件是数据源工程笔记，记录当前可用的数据接口、字段单位坑与降级路径。

## 数据源总览

| 数据类 | 主源 | 备选 | 当前状态 |
|--------|------|------|-----------|
| 日线 K 线 | akshare 腾讯源 `stock_zh_a_hist_tx` | akshare 东财 `stock_zh_a_hist`（已挂） | ✅ 主源可用 |
| 实时盘中报价 | 腾讯报价 API `qt.gtimg.cn/q=` | akshare `stock_bid_ask_em` | ✅ 腾讯 API 稳定可用 |
| 个股资讯 / 业绩 | WebSearch | — | ✅ |
| 板块表现 / 同业可比 | WebSearch | — | ✅（精确板块指数接口当前不稳，用媒体定性替代） |
| 市场环境 / 大盘风格 | WebSearch | akshare 上证指数 K 线 | ✅ |
| 北向资金 | akshare `stock_hsgt_individual_em` | — | ❌ 数据滞后至 2024-08-16，**不可用** |
| 概念归属 | akshare 东财概念接口 | 百度 PAE | ❌ 阻断，**不可用** |
| 龙虎榜 | akshare `stock_lhb_detail_em` | — | ⚠️ 接口不稳，按需重试 |
| 个股资金流分日 | akshare `stock_individual_fund_flow` | — | ⚠️ 数据返回的"最近 5 日"实际是旧数据，**不可信** |
| F10 公司资料 / 财报 | akshare `stock_individual_info_em` | mootdx | ❌ 阻断，**不可用** |
| 解禁日历 | akshare `stock_restricted_release_queue_em` | — | ⚠️ 未充分测试 |

## 关键字段单位坑（重要）

### 坑 1：akshare 腾讯源 `stock_zh_a_hist_tx` 的 `amount` 字段

- **字段名误导**：叫 `amount` 但实际是**成交量（手）**，不是成交额（万元）
- **正确换算**：成交额（元）= `amount`（手）× 收盘价 × 100
- **快速换算**：成交额（亿元）≈ `amount` × 收盘价 / 1000

**示例**：
```
三丰智能 5/14：amount=277451，close=7.02
错误解读："昨日成交 277 万元"
正确解读：成交量 27.7 万手 → 成交额 ≈ 277451 × 7.02 / 1000 ≈ 1.95 亿元
```

**Skill 输出规则**：诊断文本中**必须直接给出成交额（亿元）**，不要暴露原始 `amount` 字段。

### 坑 2：scripts/akshare_fetch.py 的 `last_amount_wan` 字段命名错误

- 脚本中字段叫 `last_amount_wan` / `avg_amount_20d_wan`，**实际是手数不是万元**
- 字段命名保持向后兼容未修复，**诊断时必须按"手"理解**

### 坑 3：腾讯实时报价 API 字段顺序

```
v_sz<code>="<market>~<name>~<code>~<现价>~<昨收>~<今开>~<成交量手>~<外盘>~<内盘>~买卖五档...~<时间戳>~<涨跌额>~<涨跌幅>~<最高>~<最低>~..."
```

**关键字段位置（0-indexed 后的人类编号）**：
- 第 4 位：现价
- 第 5 位：昨收
- 第 6 位：今开
- 第 7 位：成交量（手）
- 第 31 位：时间戳 YYYYMMDDHHMMSS
- 第 32 位：涨跌额
- 第 33 位：涨跌幅 %
- 第 34 位：当日最高
- 第 35 位：当日最低

**编码问题**：返回的公司名是 GBK 编码，curl 直接拿到的是乱码（如`锟斤拷锟斤拷`）；可用 `curl ... | iconv -f gbk -t utf-8` 解码，或者**忽略公司名**（代码已知，名称从其他来源拿）。

## 数据降级路径

### 路径 1：东财日线挂了

```
akshare stock_zh_a_hist (东财)
     ↓ Connection aborted / RemoteDisconnected
切换 stock_zh_a_hist_tx (腾讯)
     ↓ 字段调整：腾讯返回字段为 date/open/close/high/low/amount，无 volume
处理：amount 字段当成交量（手）使用，自行换算成交额
```

### 路径 2：实时盘中数据接口都挂了

```
akshare stock_bid_ask_em / stock_zh_a_spot_em (东财)
     ↓ Connection aborted
直接 curl 腾讯 qt.gtimg.cn/q= (HTTP API)
     ↓ 网络不通
fallback 到最近日线 K 线，标"截至 X-X-X 收盘"，**不再标"盘中"**
```

### 路径 3：资讯 / 政策 WebSearch 0 结果

```
WebSearch 主查询
     ↓ 0 结果或仅返回过期信息
换关键词重试（去掉日期 / 换近似术语）
     ↓ 仍 0 结果
标"近期资讯暂缺"继续，**不强行编造催化事件**
```

### 路径 4：板块 / 同业数据缺失

```
板块指数接口阻断
     ↓ 没有精确板块涨跌
WebSearch 找板块整体涨幅 + 近期媒体定性
     ↓ 仍无数据
概念/产业链段标"板块数据暂缺"，但**仍要给市场环境定性**（大盘点位仍可拉到）
```

## 接口失败必须在输出层声明（重要）

K 线接口成功 ≠ 数据完整。脚本的 `summary` 段是 K 线统计，但 `fund_flow` / `info` 等接口可能各自失败（脚本通过 try-except 兜底，将错误信息记录到 `fund_flow_error` / `info_error` 字段）。诊断输出层（IM 文本"数据备注"段）必须**显式列出失败项**，避免读者误以为数据完整。

### 输出层声明清单

每次生成诊断后，按以下清单逐项核对脚本返回的 JSON：

| JSON 字段 | 含义 | 失败时数据备注必须声明 |
|----------|------|----------------------|
| `summary` 缺失 | K 线接口失败 | "K 线数据不可用，本诊断技术面 / 资金面部分基于其他来源" |
| `fund_flow_error` 存在 | 资金流接口失败 | "个股资金流接口失败，资金面段基于 K 线 amount × 收盘价自算成交额，不含主力净流入数据" |
| `info_error` 存在 | F10 公司资料失败 | "公司名 / 总股本 / 流通股本接口失败，市值 / PE / PB 估算基于公开报道补全或标注暂缺" |
| `name == code` | 股票名退化为代码 | "公司名接口失败，本诊断仅以代码 <code> 标识，未交叉验证名称" |

### 反例（不要这样写）

```
数据备注：本诊断基于 2026-05-15 收盘行情数据（akshare 腾讯源）。
```
（用户读到这一行，会默认所有维度数据完整。如果资金面其实是 amount 自算 / 资金流接口失败，这一行就误导。）

### 正例

```
数据备注：本诊断基于 2026-05-15 收盘行情数据（akshare 腾讯源），K 线接口成功；个股资金流接口（stock_individual_fund_flow）当次返回失败，【资金面】成交额为 K 线 amount × 收盘价自算，未含主力净流入数据；公司资料接口（stock_individual_info_em）失败，市值 / PB 数据基于公开报道补全（据 XXX）。
```

### 与 Step 6 自检的关联

`SKILL.md` Step 6 "交付前自检" 的合规底线检查时，应顺带核对：诊断里若出现"市值 / 主力净流入 / 公司全称"等字段，必须能在脚本 JSON 或公开报道里找到，否则在数据备注声明数据来源。

## 数据时效性约束

| 数据 | 最佳时效 | 兜底口径 |
|------|---------|---------|
| 日线 K 线 | T 日 15:00 收盘后 | T-1 收盘 |
| 实时盘中报价 | 当前时刻（≤ 1 分钟延迟） | 当日尾盘 |
| 个股资讯 | 当周内 | 近 30 日 |
| 板块表现 | 当日 | 近 7 日 |
| 政策催化 | 季度内 | 半年内 |
| 业绩数据 | 最近一份季报 | 上一份季报 |

**Skill 输出规则**：诊断文本顶部必须明确标注 `截至 YYYY-MM-DD HH:MM 盘中` 或 `截至 YYYY-MM-DD 收盘`。

## 时区与交易时段处理

- A 股交易时段（北京时间）：09:30-11:30、13:00-15:00
- 系统时间可能与北京时间存在时区差（如本机记录 2026-05-14，北京时间已经是 2026-05-15）
- **判断诊断时间**：以**腾讯实时报价 API 返回的时间戳**为准，不要依赖本机 `datetime.now()`

## 脚本使用

### 依赖

- Python 3.10+
- akshare ≥ 1.17（脚本实测版本 1.17.21）
- pandas（akshare 依赖项，pip install akshare 时自动安装）

首次环境检查：

```bash
python3 -c "import akshare; print(akshare.__version__)"
# 若 ModuleNotFoundError：
pip install "akshare>=1.17"
```

### 调用示例

```bash
# 拉单只历史 K 线（60-120 日）+ 字段统计
python3 scripts/akshare_fetch.py 300276

# 落盘位置
/tmp/stock-radar/<code>.json
```

### 调用约定（重要）

- 脚本头部是 docstring 而非 shebang，**不可执行 chmod +x 后直接跑**，必须以 `python3` 调用
- 输出环境变量 `STOCK_RADAR_OUT_DIR` 可覆盖默认落盘目录 `/tmp/stock-radar/`
- 只接受 1 个或 2 个位置参数：`<code>` 或 `<code> <name>`；省略 name 时脚本会尝试从 akshare 拉取（可能因接口失败而退化为代码本身，见下节"接口失败必须在输出层声明"）

腾讯实时报价（手动调用，未封装到脚本）：

```bash
curl -s "https://qt.gtimg.cn/q=sz300276,sh600519,sz300308"
# 多只票一次拉，按 v_<market><code> 解析
```
