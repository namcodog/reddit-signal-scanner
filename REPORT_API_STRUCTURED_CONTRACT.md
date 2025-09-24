# 报告 API 结构化洞察联调手册（P0 落地版）

> 适用于 `GET /api/v1/report/{task_id}`（`format=full|summary|insights`）以及导出相关接口

## 🚀 使用方法总览

- **查询接口**：`GET /api/v1/report/{task_id}?format=full`
- **导出准备**：`GET /api/v1/report/{task_id}/export?format=json|csv|pdf`
- **导出下载**：`GET /api/v1/report/{task_id}/download?token={token}`（一次性）

当前后端已补齐结构化洞察字段，任何非 demo 模式请求都会返回真实数据集；若主流程缺稿，会自动回落到 demo 模拟数据，字段结构保持一致。

## 📡 数据来源说明（P1 分析结果已接通）

- 分析引擎在任务完成时会向 `analyses.insights` 写入结构化 JSON，字段覆盖痛点/竞品/机会与摘要指标。
- `report_formatter` 会对该 JSON 做兜底、排序、补全摘要指标，并产出本页展示的结构；若某字段缺省，将返回默认值（空对象/数组或 0）。
- 若需要复查原始数据，可在数据库中查询：

  ```sql
  select insights
  from analyses
  where task_id = '<task_uuid>';
  ```

- 关键字段映射关系：

  | `analyses.insights` 字段 | 报告输出 | 说明 |
  | --- | --- | --- |
  | `pain_points[]` | `data.pain_points[]` | 直接映射；补齐 `severity`、示例帖子等默认值 |
  | `competitors[]` | `data.competitors[]` | 计算 `share_of_voice`、缺省总结文本 |
  | `opportunities[]` | `data.opportunities[]` | 保留评分字段，补齐默认标签 |
  | `analysis_summary.executive_summary` | `data.executive_summary` | 若缺失，后端按关键洞察生成摘要 |
  | `analysis_summary.market_metrics` | `data.market_metrics` | 若缺失，后端依据 `sources` 推算提及量等 |

这样前端拿到的 JSON 已经是 P0+P1 联调后的稳定契约。

## ✅ 响应示例（格式：`full`）

```json
{
  "status": "success",
  "message": "分析报告获取成功（full格式）",
  "timestamp": "2025-09-23T10:00:00Z",
  "data": {
    "task_id": "tsk_demo_001",
    "query": "寻找 Reddit 营销自动化机会",
    "total_posts": 120,
    "total_comments": 340,
    "analysis_duration": 142.5,
    "key_insights": [
      {
        "title": "营销自动化需求强烈",
        "content": "大量用户提到需要自动化工具以节省时间。",
        "confidence": 0.9,
        "source_count": 24,
        "tags": ["automation", "growth"]
      }
    ],
    "sentiment_summary": {
      "positive": 0.62,
      "neutral": 0.25,
      "negative": 0.13
    },
    "trending_topics": ["workflow", "ai assistant"],
    "user_personas": [
      {
        "name": "增长负责人",
        "pain_points": ["缺少自动化工具"],
        "priority": "high"
      }
    ],
    "generated_at": "2025-09-23T10:00:00Z",
    "data_freshness": "6小时内",
    "executive_summary": {
      "headline": "Reddit 营销自动化趋势洞察",
      "total_communities": 18,
      "key_insights": 5,
      "top_opportunity": "自动化运营中小社区",
      "confidence_score": 0.82,
      "summary_points": [
        "用户对自动化工具的兴趣持续走高",
        "竞品在价格策略上存在空档"
      ]
    },
    "market_metrics": {
      "total_mentions": 460,
      "sentiment_score": 0.37,
      "top_communities": ["r/startups", "r/marketing"],
      "trending_keywords": ["automation", "reddit bot"],
      "engagement_rate": 0.41,
      "sample_size": 180
    },
    "pain_points": [
      {
        "description": "缺少一体化 Reddit 营销工具",
        "sentiment_score": -0.32,
        "frequency": 28,
        "confidence": 0.78,
        "severity": "high",
        "categories": ["效率", "工具缺口"],
        "tags": ["automation", "campaign"],
        "example_posts": [
          {
            "post_id": "abc123",
            "community": "r/startups",
            "permalink": "https://reddit.com/abc123",
            "content_snippet": "有没有一体化的 Reddit 营销工具？",
            "upvotes": 156
          }
        ]
      }
    ],
    "competitors": [
      {
        "name": "CompetitorX",
        "mention_count": 45,
        "sentiment_score": 0.18,
        "strengths": ["自动化流程完善"],
        "weaknesses": ["价格昂贵"],
        "price_mentions": ["$199/mo"],
        "market_position": "leader",
        "share_of_voice": 0.33,
        "summary": "高端定位但价格较高",
        "website": "https://competitor.example"
      }
    ],
    "opportunities": [
      {
        "title": "面向中小企业的 Reddit 自动化套件",
        "description": "推出可负担的 Reddit 自动化工具，降低使用门槛。",
        "market_size_indicator": "large",
        "urgency_score": 0.74,
        "feasibility_score": 0.68,
        "target_communities": ["r/smallbusiness", "r/marketing"],
        "related_keywords": ["automation", "smb"],
        "estimated_demand": 520,
        "potential_score": 0.81,
        "timeframe": "Q4"
      }
    ]
  }
}
```

## 📚 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `executive_summary.headline` | `string?` | 报告主标题，可为空 |
| `executive_summary.total_communities` | `number` | 参与分析的社区数量 |
| `executive_summary.key_insights` | `number` | 关键洞察条目数 |
| `executive_summary.top_opportunity` | `string?` | 系统评估的最佳机会 |
| `executive_summary.confidence_score` | `number? (0-1)` | 报告整体置信度 |
| `executive_summary.summary_points` | `string[]` | 1~3 条要点摘要 |
| `market_metrics.total_mentions` | `number` | 帖子数 + 评论数 |
| `market_metrics.sentiment_score` | `number (-1~1)` | 正负向差值（正 - 负） |
| `market_metrics.top_communities` | `string[]` | 热门社区列表 |
| `market_metrics.trending_keywords` | `string[]` | 高频关键词 |
| `market_metrics.engagement_rate` | `number? (0-1)` | 互动率，若无法统计返回空 |
| `market_metrics.sample_size` | `number?` | 有效样本数量（posts） |
| `pain_points[].description` | `string` | 用户痛点描述 |
| `pain_points[].sentiment_score` | `number (-1~1)` | 情感强度（负值越痛） |
| `pain_points[].frequency` | `number` | 提及次数 |
| `pain_points[].confidence` | `number?` | 算法置信度（0-1，可选） |
| `pain_points[].severity` | `"low"\|"medium"\|"high"` | 严重程度标签 |
| `pain_points[].categories` | `string[]` | 痛点分类标签 |
| `pain_points[].tags` | `string[]` | 主题关键词 |
| `pain_points[].example_posts[]` | `object` | 证据帖：`post_id`、`community`、`permalink?`、`content_snippet`、`upvotes?` |
| `competitors[].name` | `string` | 竞品名称 |
| `competitors[].mention_count` | `number` | 提及次数 |
| `competitors[].sentiment_score` | `number (-1~1)` | 情感趋势 |
| `competitors[].strengths` / `weaknesses` | `string[]` | 优劣势列表 |
| `competitors[].price_mentions` | `string[]` | 价格相关提及 |
| `competitors[].market_position` | `leader\|challenger\|niche\|unknown` | 市场定位 |
| `competitors[].share_of_voice` | `number (0-1)` | 竞品声量占比（自动计算） |
| `competitors[].summary` | `string` | 简要总结 |
| `competitors[].website` | `string?` | 官网链接 |
| `opportunities[].title` | `string` | 机会标题 |
| `opportunities[].description` | `string` | 机会描述 |
| `opportunities[].market_size_indicator` | `tiny/small/medium/large/huge/unknown` | 市场规模指标 |
| `opportunities[].urgency_score` | `number (0-1)` | 紧迫程度 |
| `opportunities[].feasibility_score` | `number (0-1)` | 可行性评估 |
| `opportunities[].target_communities` | `string[]` | 推荐切入社区 |
| `opportunities[].related_keywords` | `string[]` | 关键词 |
| `opportunities[].estimated_demand` | `number?` | 需求量估算 |
| `opportunities[].potential_score` | `number? (0-1)` | 综合潜力评分 |
| `opportunities[].timeframe` | `string?` | 建议落地时间窗口 |

> 备注：所有新增结构在 Pydantic 层严格校验；若后端暂时缺字段，会回传相应默认值（空对象/空数组/0）。

## 💡 前端接入提示

- TypeScript 契约位于 `frontend/src/types/contracts/report.contract.ts`，已同步字段。
- `market_metrics.sentiment_score` 表示正向减负向，可直接用于可视化；若需要比例请结合 `sentiment_summary`。
- `pain_points[].example_posts` 仅截取最多 5 条例子，`content_snippet` 已做 140 字截断，可直接渲染。
- `share_of_voice` 自动换算为 0~1，可乘以 100 显示百分比。
- 若需要兜底 UI，可检测列表长度为 0 时展示空状态。

### 前端联调 Checklist（P1+P0 对齐）

1. **移除 mock**：`InsightsReport`、`ExecutiveSummary` 等组件不再引用 `defaultInsightData`；所有数据来源均改为 `reportService.getReport` 返回值。
2. **字段绑定**：
   - `ExecutiveSummary` → `report.executive_summary` + 总帖子/评论数 + 情感摘要。
   - `PainPointsList` → `report.pain_points`；渲染 `severity`、`example_posts`、`tags`。
   - `CompetitorAnalysis` → `report.competitors`；优先展示 `share_of_voice`，缺省时用 `mention_count` 计算。
   - `OpportunityMatrix` → `report.opportunities`；展示 `urgency_score`、`feasibility_score`、`timeframe` 等轴心信息。
   - `MarketMetricsWidget`（如需新增卡片）→ `report.market_metrics`（total_mentions / engagement_rate / top_communities / trending_keywords）。
3. **骨架与空态**：字段为空时显示 loading skeleton 或“暂无数据”提示，避免访问 undefined。
4. **指标展示**：`sentiment_summary` 用于情感分布图；仪表盘使用 `market_metrics.sentiment_score`。
5. **交互埋点**：
   - 查看原帖、复制链接等操作 → `event_type=analysis_interaction`（附 `task_id`、`section`、`item_id`）。
   - 报告首屏渲染耗时 → `event_type=metric`，`metric_name=report_first_paint_ms`。
6. **错误兜底**：当 API 返回 404/500 时沿用既有错误页；若 `status` 轮询未完成，报告页应自动重拉数据以防旧缓存。
7. **本地验证**：使用 `docs/reports/sample_report_response.json` 作为 mock 或照说明跑 `python tests/ci/test_runner.py report` 掌握结构；完成后运行 `make quick-gate-local` 确认质量门。

## 🧪 本地验证建议

```bash
# 后端类型 & smoke
make type-check
make backend-smoke

# 前端组件用例
cd frontend && npm test -- --run src/__tests__/components src/__tests__/hooks src/__tests__/utils

# 手动调试示例
curl "http://localhost:8000/api/v1/report/{task_id}?format=full" | jq
```

> 如果主流程任务还未生成结构化数据，可临时使用 demo 模式：`ENABLE_DEMO_ANALYSIS_SIMULATOR=true DEMO_SIMULATOR_FORCE_ONLY=true uvicorn ...`

## 🔄 导出接口补充

- 准备阶段返回 `download_url` + `token`，有效期 1 小时，下载一次后自动失效。
- `estimated_size_kb` 为后端估算，前端可用于进度提示。
- 下载接口直接返回二进制流（`application/json` / `text/csv` / `application/pdf`），记得添加 `Accept` 头或根据 `content_type` 处理。

---

若联调过程中发现字段缺失或含义不清，请在 Slack #v0-integration 标注 `@backend`，我们会同步排查。祝联调顺利 ✨
