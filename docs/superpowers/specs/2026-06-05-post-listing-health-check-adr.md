# ADR：上架后健康检查（Post-Listing Health Check）

**状态**：阶段二前瞻（未实现调度）

## 背景

首次准入使用 `evaluation_mode=capability_full`。上架后需 Golden Case 巡检，不替代首次 PASS。

## 决策

1. **触发**：定时 / 上架后 N 天 / 运营手动（阶段三接入）
2. **模式**：`evaluation_mode=post_listing_health_check`（枚举已预留）
3. **结论**：告警、降权、人工工单；不自动撤销 PASS
4. **数据**：复用 `evaluation_runs`、`model_votes`、`stage_timings`
5. **API 预留**：`GET /eval/history?evaluation_mode=post_listing_health_check`

## 非目标（本阶段）

- 定时任务引擎
- 集市降权自动化
