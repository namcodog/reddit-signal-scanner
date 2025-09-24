# REPORT_API_STRUCTURED_CONTRACT

该文档描述 `/api/v1/report/{task_id}` 接口返回的结构化商业洞察报告契约，为前后端及 QA 提供统一参考。

## 1. 请求说明

- **Method**: `GET`
- **Path**: `/api/v1/report/{task_id}`
- **Query**: `format=full|summary|insights`（默认 `full`）
- **Headers**: `Authorization: Bearer <JWT>`

## 2. 响应包装

所有格式返回统一 `SuccessResponse<T>`：

```jsonc
{
  "status": "success",
  "message": "分析报告获取成功（full格式）",
  "timestamp": "2025-09-24T06:48:54.027695Z",
  "data": { /* ReportData */ }
}
```

## 3. ReportData 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `task_id` | `string` | 对应任务 UUID，demo 模式为 `demo-*` |
| `query` | `string` | 用户输入的产品描述（已裁剪至 2k 字符） |
| `total_posts` | `number` | 参与分析的 Reddit 帖子数量 |
| `total_comments` | `number` | 参与分析的评论数量 |
| `analysis_duration` | `number` | 分析耗时（秒） |
| `confidence_score` | `number` | 0-1 之间的整体置信度 |
| `key_insights` | `InsightItem[]` | 聚合洞察摘要列表 |
| `sentiment_summary` | `Record<string, number>` | 情感分布（`positive/neutral/negative`） |
| `trending_topics` | `string[]` | 高频话题关键词 |
| `user_personas` | `Array<Record<string, unknown>>` | 画像列表（可为空数组） |
| `generated_at` | `string` | ISO-8601 时间，UTC，带 `Z` |
| `data_freshness` | `string` | 数据新鲜度文案（例如 `1小时内`） |
| `html_content` | `string` | 预渲染报告 HTML（可选） |
| `executive_summary` | `ExecutiveSummary` | 执行摘要板块 |
| `market_metrics` | `MarketMetrics` | 市场指标板块 |
| `pain_points` | `PainPointInsight[]` | 用户痛点列表（允许空数组） |
| `competitors` | `CompetitorInsight[]` | 竞品情报列表（允许空数组） |
| `opportunities` | `OpportunityInsight[]` | 商业机会列表（允许空数组） |
| `data_coverage` | `Record<string, number>` | 覆盖统计（社区数量、缓存命中率等） |

> 所有数组字段**至少返回空数组**，不会省略或返回 `null`。

## 4. 嵌套结构

### 4.1 ExecutiveSummary

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `headline` | `string \| null` | 概要标题 |
| `total_communities` | `number` | 覆盖社区数量 |
| `key_insights` | `number` | 关键洞察总数 |
| `top_opportunity` | `string \| null` | 最高优先级机会 |
| `confidence_score` | `number` | 与顶层一致的置信度 |
| `summary_points` | `string[]` | 3 条以内的要点摘要 |

### 4.2 MarketMetrics

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `total_mentions` | `number` | 帖子 + 评论总量 |
| `sentiment_score` | `number` | 情感得分（-1 ~ 1） |
| `top_communities` | `string[]` | 高频社区列表 |
| `trending_keywords` | `string[]` | 高频关键词 |
| `sample_size` | `number` | 样本量（与 `total_mentions` 协同） |
| `engagement_rate` | `number` | 互动率（0 ~ 1，可为 0） |

### 4.3 PainPointInsight

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `description` | `string` | 痛点描述 |
| `sentiment_score` | `number` | 情感得分（-1 ~ 1） |
| `frequency` | `number` | 提及次数 |
| `confidence` | `number` | 洞察置信度（0 ~ 1） |
| `severity` | `'low' \| 'medium' \| 'high' \| 'unknown'` | 严重程度标签 |
| `categories` | `string[]` | 主题分类 |
| `example_posts` | `Array<PainPointExample>` | 证据帖子（允许空数组） |
| `tags` | `string[]` | 自定义标签 |

### 4.4 CompetitorInsight

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `string` | 竞品名称 |
| `market_position` | `'leader' \| 'challenger' \| 'follower' \| 'niche' \| 'unknown'` | 市场定位 |
| `mention_count` | `number` | 提及次数 |
| `sentiment_score` | `number` | 情感分数 |
| `strengths` | `string[]` | 优势 |
| `weaknesses` | `string[]` | 劣势 |
| `market_share_estimate` | `number \| null` | 份额估计（可缺省） |

### 4.5 OpportunityInsight

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `string` | 机会标题 |
| `description` | `string` | 详细描述 |
| `market_size_indicator` | `'tiny' \| 'small' \| 'medium' \| 'large' \| 'huge' \| 'unknown'` | 市场规模等级 |
| `urgency_score` | `number` | 紧迫度（0 ~ 1） |
| `feasibility_score` | `number` | 可行度（0 ~ 1） |
| `target_communities` | `string[]` | 目标社区 |
| `related_keywords` | `string[]` | 相关关键词 |
| `estimated_demand` | `number \| null` | 预估需求量 |

## 5. 示例（真实数据）

详见 `docs/PRD/PRD-05-前端交互.md` 第 3.5 节“真实数据绑定与契约校验”中的 JSON 示例，可直接作为集成或 Postman 参考。

## 6. 验收清单

- [x] `tests/integration/test_report_endpoint.py` 断言上述字段全部存在且类型正确。
- [x] 前端 `ReportPageV0`、`ExecutiveSummary` 等组件仅消费 `ReportData`，无 mock 依赖。
- [x] `npm run type-check` 通过，确保 TypeScript 契约与后端对齐。
- [ ] `make quick-gate-local` 将在类型问题解决后保持全绿（当前 mypy 测试基线仍需清理）。

