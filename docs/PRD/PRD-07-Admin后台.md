文档版本：v1.0
最后更新：2025‑09‑16
适用范围：与 PRD‑01~08 配套；仅覆盖 Admin 的 MVP 能力：
1）社区验收；2）算法验收；3）用户反馈汇总与回流；4）配置补丁（YAML Patch）生成与合并。

⸻

1. 背景与问题
	•	当前 Admin 过度开发，未聚焦关键闭环：社区是否值得长期监控、算法产出是否可交付、真实用户如何反馈修正。
	•	现阶段仅内部人员使用（产品/运营），无需复杂大盘与实验平台。
	•	真相源（监控社区列表）存放在 Git 配置，不直接写库；需要“事件记录 + Patch 生成 + 合并后生效”的工作流。

⸻

2. 目标（MVP 的 KR）
	•	KR1：社区池可控：任意一天，完成对新/边缘社区的人工审查与决策，生成 Patch 并合并；黑名单社区在下一次分析中不再出现；新增核心社区被纳入抓取与分析。
	•	KR2：算法验收可判：每次任务具备门槛判定（✔/✖）与 A‑Score，能一键重跑（仅核心社区）；连续失败自动提示“需调参”。
	•	KR3：用户反馈可用：前台“赞/踩+原因”与洞察标注汇总在 Admin 可见，支持按原因回看样本任务。
	•	KR4：闭环留痕：所有决策与反馈落到统一事件表，可审计、可回滚。

⸻

3. 非目标（MVP 不做）
	•	不做复杂效果大盘、A/B 管理、在线调参台。
	•	不做跨模型横评面板。
	•	不做可视化图表（先表格 + 简单指标）。

⸻

4. 角色与权限
	•	Admin：产品/运营（内部）可访问 /admin/*；可查看与操作；可导出 Patch。
	•	匿名/普通用户：仅产生用户反馈事件（前台埋点），不能访问 /admin/*。
	•	认证沿用 PRD‑06；鉴权规则：非 Admin 角色拒绝访问（HTTP 403）。

⸻

5. 关键术语
	•	C‑Score：社区综合评分（0~100），由相关度、活跃度、新鲜度、低垃圾、低去重加权。
	•	A‑Score：一次任务/报告的质量评分（0~100），由相关性、覆盖广度、证据强度、新鲜度、清洁度、多样性加权。
	•	Must Gates（必选门槛）：硬性阈值；任一不达标即“不通过”。
	•	YAML Patch：Admin 的社区决策汇总成配置补丁，由人或机器人合并到 Git 仓库后生效。
	•	反馈事件：统一写入 feedback_events 表，承载社区决策、算法验收、用户赞/踩、洞察标注等。

⸻

6. 整体流程（文字版时序）
	1.	定时/手动拉取社区与任务数据 → Admin 三页展示（社区验收 / 算法验收 / 用户反馈）。
	2.	程序先算灯号与分数（C‑Score / A‑Score + Must Gates）。
	3.	人工抽检与决策：
	•	社区：通过/实验/黑名单 + 标签 → 生成 community_decision 事件 → 导出 YAML Patch → 合并。
	•	算法：满意/不满意 + 失败原因 → 记录 analysis_rating → 不通过可“仅核心社区重跑”。
	•	用户：汇总前台赞/踩、标注等事件，辅助判断“问题出在召回/去噪/摘要哪一环”。
	4.	合并 Patch 后，下一次分析读取最新配置；事件沉淀用于周度阈值微调与审计。

⸻

7. 信息架构（仅三页）

7.1 社区验收（目标①）

表格列
社区名 | hit_7d | last_crawled_at | dup_ratio | spam_ratio | topic_score | C‑Score | 状态灯 | 当前标签 | 证据

操作
	•	通过/核心、进实验、暂停/黑名单、打标签（状态/主题/风险）、新增社区（手输标识）
	•	右上角：生成 YAML Patch（预览/下载/一键开 PR）

筛选/排序
	•	筛：红/黄/绿、标签、活跃度区间
	•	排：C‑Score 降序、近7天命中数降序

抽检按钮
	•	抽样3条：打开 3~5 条样例贴链接窗口（仅链接与元信息）

7.2 算法验收（目标②）

列表列
task_id | 开始时间 | 用时 | 覆盖社区数 | A‑Score | Must Gates(✔/✖) | 满意度 | 操作

详情侧栏
	•	关键指标：evidence_coverage、fresh_median_days、relevance_pass_rate、dup_ratio、spam_ratio、evidence_per_insight_avg、diversity_score
	•	失败原因 Top3（近 30 天统计）
	•	按钮：满意/不满意（枚举原因）、仅核心社区重跑

7.3 用户反馈（目标③）

汇总卡片
	•	近 30 天：用户赞/踩比、完成阅读率、不满原因 Top5、被标注最多的洞察类型
	•	可点击某原因 → 拉出最近 10 条相关任务做抽样回看

⸻

8. 规则与阈值（实现口径）

8.1 社区验证（Must + C‑Score）

Must Gates（任一失败判红）
	•	freshness_hours_max = 48
	•	min_hits_7d = 30
	•	max_dup_ratio = 0.15
	•	max_spam_ratio = 0.10
	•	min_topic_score = 0.60

C‑Score 计算（0~100）
C = 35%*topic + 25%*activity + 20%*freshness + 10%*(1-spam) + 10%*(1-dup)
activity = min(hit_7d/50,1)*100
freshness = max(0,1-hours_since_last_crawl/48)*100
topic = topic_score*100

阈值与动作
	•	C ≥ 70 连续两周 → 核心
	•	55 ≤ C < 70 → 实验（观察两周）
	•	< 55 或 Must 失败 → 黑名单/暂停

8.2 算法验证（Must + A‑Score）

Must Gates
	•	evidence_coverage ≥ 0.80
	•	fresh_median_days ≤ 7
	•	relevance_pass_rate ≥ 0.70
	•	dup_ratio ≤ 0.15
	•	安全合规通过（PII/NSFW脱敏）

A‑Score 计算（0~100）

A = 30%*relevance + 20%*coverage + 20%*evidence_strength + 15%*freshness + 10%*cleanliness + 5%*diversity
where:
- relevance = 平均洞察相关性分（0~100）
- coverage = 目标主题Top-K覆盖率（K=10，0~100）
- evidence_strength = min(2, 证据数均值)/2 * 100
- freshness = max(0,1 - median_days/7)*100
- cleanliness = 100*(1-dup_ratio)*(1-spam_ratio)
- diversity = (1 - Σ source_share^2) 映射到 0~100

阈值与动作
	•	A ≥ 75 → 通过并留档
	•	60 ≤ A < 75 → Beta（边交付边收集反馈）
	•	< 60 或 Must 失败 → 不通过，默认“仅核心社区重跑”
	•	连续 3 次不通过 → 弹出“需调参/规则修正”提醒

失败原因枚举
覆盖率低 | 不相关 | 证据不足 | 样本过旧 | 重复/噪声高 | 总结太泛

⸻

9. 数据模型（最小改动）

9.1 统一反馈事件表 feedback_events（PostgreSQL）

CREATE TABLE feedback_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL CHECK (source IN ('admin','user')),
  event_type TEXT NOT NULL CHECK (event_type IN ('community_decision','analysis_rating','insight_flag','metric')),
  user_id UUID NULL,
  task_id UUID NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 常用索引
CREATE INDEX idx_feedback_events_type_time ON feedback_events(event_type, created_at DESC);
CREATE INDEX idx_feedback_events_task ON feedback_events(task_id);
CREATE INDEX idx_feedback_events_payload_community ON feedback_events ((payload->>'community'));

payload 约定
	•	community_decision：{community, action:'approve|experiment|pause|blacklist', labels:[…], reason, actor}
	•	analysis_rating：{is_satisfied:boolean, reasons:[…], notes}
	•	insight_flag：{insight_id, flag:'不相关|错误', notes}
	•	metric：{metric:'dwell_seconds'|'read_complete', value:number}

不新增社区主数据表；监控社区依旧以 Git 配置为真相源。

9.2 视图/物化视图（建议）
	•	vw_community_7d：近 7 天的 hit_7d / dup_ratio / spam_ratio / topic_score / last_crawled_at 聚合视图
	•	vw_analysis_metrics：每个 task_id 的 Must 指标与 A‑Score 预计算结果（或实时计算）

⸻

10. API 设计（MVP 必要 5 个 + 1 个聚合）

所有响应统一包一层：{ "code":0, "data":{…}, "trace_id":"…" }；错误 code != 0 并带 message。

10.1 GET /admin/communities/summary

用途：社区页表格数据（含灯号与 C‑Score）。
查询参数：q? status?=green|yellow|red tag? sort?=cscore_desc|hit_desc page?=1 page_size?=50
响应示例

{
  "code": 0,
  "data": {
    "items": [
      {
        "community": "r/startups",
        "hit_7d": 83,
        "last_crawled_at": "2025-09-15T11:20:00Z",
        "dup_ratio": 0.08,
        "spam_ratio": 0.06,
        "topic_score": 0.74,
        "c_score": 82,
        "status_color": "green",
        "labels": ["状态:核心","主题:创业"],
        "evidence_samples": [
          "https://reddit.com/…1",
          "https://reddit.com/…2",
          "https://reddit.com/…3"
        ]
      }
    ],
    "total": 245
  }
}
10.2 POST /admin/decisions/community

用途：记录一次社区决策（写入 feedback_events），不直接改配置。
请求体

{
  "community": "r/technology",
  "action": "blacklist",
  "labels": ["状态:黑名单","风险:广告多"],
  "reason": "垃圾率高且与主题不符"
}
响应
{ "code": 0, "data": { "event_id": "uuid-..." } }

10.3 GET /admin/config/patch

用途：汇总最近的 community_decision 事件生成 YAML Patch（文本下载）。
参数：since?=ISO8601（缺省=24h 内）
响应（Content-Type: text/yaml）：返回文本，如：
core:
  - r/startups
experimental:
  - r/ArtificialIntelligence
blacklist:
  - r/technology
labels:
  r/startups: ["主题:创业","状态:核心"]
  r/technology: ["状态:黑名单","风险:广告多"]

备选：POST /admin/config/patch/pr（可选）在有 Token 的情况下自动开 PR。

10.4 POST /admin/feedback/analysis

用途：Admin 对任务的满意/不满意与原因（写 feedback_events）。
请求体

{
  "task_id": "uuid-...",
  "is_satisfied": false,
  "reasons": ["覆盖率低","重复/噪声高"],
  "notes": "建议仅核心社区重跑"
}

响应：{ "code":0, "data": { "event_id":"uuid-..." } }

10.5 GET /admin/feedback/summary?days=30

用途：用户与 Admin 的反馈汇总。
响应

{
  "code": 0,
  "data": {
    "analysis_satisfaction_rate": 0.68,
    "top_fail_reasons": [
      {"reason":"覆盖率低","count":21},
      {"reason":"不相关","count":18}
    ],
    "user_like_ratio": 0.61,
    "read_complete_rate": 0.47,
    "top_flagged_insight_types": [
      {"type":"不相关","count":33}
    ]
  }
}

10.6（聚合）GET /admin/analysis/{task_id}

用途：返回该任务的 QA 指标与 A‑Score（方便前端详情侧栏展示）。
响应

{
  "code": 0,
  "data": {
    "task_id": "uuid-...",
    "must": {
      "evidence_coverage": 0.86,
      "fresh_median_days": 3,
      "relevance_pass_rate": 0.74,
      "dup_ratio": 0.12,
      "safety_pass": true
    },
    "metrics": {
      "evidence_per_insight_avg": 1.7,
      "diversity_score": 62
    },
    "a_score": 78,
    "must_pass": true
  }
}

重跑沿用 PRD‑04 的任务创建接口：POST /tasks/{task_id}/rerun?core_only=true

⸻

11. 前端规格（页面级）

11.1 社区验收页
	•	表格列：见 7.1。
	•	行内操作：通过/实验/暂停/黑名单/打标签/证据。
	•	顶部操作：筛选器、排序器、生成 Patch。
	•	空态：提示“暂无候选社区，去新增或扩大抓取策略”。
	•	错误态：请求失败显示 trace_id 与“重试”按钮。

11.2 算法验收页
	•	列表列：见 7.2。
	•	详情侧栏：Must Gates ✔/✖、A‑Score、关键指标与“失败原因 Top3”。
	•	行内操作：满意/不满意（必选原因）、仅核心社区重跑。
	•	抽样按钮：随机抽样10条洞察 展示证据链接。

11.3 用户反馈页
	•	汇总卡片 + 原因列表；点击原因下钻最近 10 条任务。
	•	支持按日期范围筛选。

⸻

12. 埋点要求（前台+Admin）

12.1 前台（配合 PRD‑05）
	•	analysis_rating：{is_satisfied, reasons[], task_id}
	•	metric：{metric:'dwell_seconds'|'read_complete', value}
	•	insight_flag：{insight_id, flag, notes?}

12.2 Admin
	•	community_decision：每次动作都写事件
	•	analysis_rating：满意/不满意与原因
	•	页面性能：加载耗时（仅日志，不上报三方）

⸻

13. YAML Patch 规范（MVP）

core:            # 列表：加入核心监控
  - r/startups
experimental:    # 列表：进入实验
  - r/ArtificialIntelligence
blacklist:       # 列表：暂停/黑名单
  - r/technology
labels:          # 可选：社区标签
  r/startups: ["主题:创业","状态:核心"]
  r/technology: ["状态:黑名单","风险:广告多"]

# 可选：审计字段（便于回溯）
_meta:
  patch_id: "2025-09-16T10:00:00Z-ops-key"
  actor: "key@company.com"
  comment: "垃圾率高且不相关"

14. 人工验证 SOP（落地法）
	•	社区：红灯全检、黄灯抽 50%、绿灯抽 10%，每个 ≤3 分钟；动作后导出 Patch 并合并。
	•	算法：先看 Must ✔/✖；抽样 10 条洞察看证据；A‑Score ≥75 通过，60~74 Beta，<60 不通过并重跑。
	•	模板：
	•	社区抽检模板 CSV
	•	算法/报告抽检模板 CSV

⸻

15. E2E 验收用例（写入 PRD‑08）
	1.	社区验收流：决策→Patch→合并→下一次分析按配置生效。
	2.	社区回滚：移出→合并→缺失→恢复→合并→恢复命中。
	3.	算法不通过纠偏：记录原因→仅核心重跑→指标改善或提示需调参。
	4.	用户反馈采集：前台踩/标注→Admin 汇总可见。
	5.	洞察标注聚合：被标注最多的类型在 30 天榜单可见。
	6.	权限与隐私：非 Admin 403；样例贴仅展示链接与元信息。
	7.	指标一致性：Admin 显示的 C‑Score/A‑Score 与后端计算一致。
	8.	Patch 审计：Patch 含 _meta 审计信息，可追溯到决策事件 id。

⸻

16. 非功能需求
	•	性能：
	•	/admin/communities/summary 首屏 ≤ 1s（1k 行以内）；分页 50 条/页。
	•	/admin/analysis/{task_id} ≤ 800ms（缓存或预计算）。
	•	稳定性：API 99.9% 月可用。
	•	安全：所有 /admin/* 需 Token；操作写事件；不泄露 PII/NSFW 原文。
	•	可观测：每个请求输出 trace_id；关键错误带原因栈。

⸻

17. 里程碑与交付
	•	M1（后端 / 3 天）：feedback_events 表上线 + 5 个 API + 聚合接口。
	•	M2（前端 / 3 天）：三页表格 + 详情侧栏 + 操作按钮 + Patch 预览下载。
	•	M3（集成 / 2 天）：与任务系统重跑联调；前台埋点落库联调。
	•	M4（E2E / 1 天）：8 条用例通过，上线验收。

⸻

18. 风险与应对
	•	阈值不稳 → 采用分位数自适应（周更），并保留手工固定值开关。
	•	事件泛滥 → 以 since 拉取增量生成 Patch；事件保留期 90 天，冷数据归档。
	•	Git 合并冲突 → Patch 以“增量 + 去重”生成；失败时回退到“下载手工合并”。

⸻

19. 附录

19.1 配置（示例）
community_qa:
  freshness_hours_max: 48
  min_hits_7d: 30
  max_dup_ratio: 0.15
  max_spam_ratio: 0.10
  min_topic_score: 0.60
  cscore_weights: {topic: 0.35, activity: 0.25, freshness: 0.20, anti_spam: 0.10, anti_dup: 0.10}
  cscore_thresholds: {core: 70, exp: 55}

analysis_qa:
  must:
    min_evidence_coverage: 0.80
    max_fresh_median_days: 7
    min_relevance_pass_rate: 0.70
    max_dup_ratio: 0.15
    safety: {enforce_pii_scrub: true, enforce_nsfw_block: true}
  ascore_weights: {relevance: 0.30, coverage: 0.20, evidence: 0.20, freshness: 0.15, cleanliness: 0.10, diversity: 0.05}
  ascore_thresholds: {pass: 75, beta: 60}
  rerun_policy: {core_only_on_fail: true, max_consecutive_fail: 3}

  19.2 计算伪代码

  def c_score(hit_7d, last_crawled_hours, dup_ratio, spam_ratio, topic_score):
    activity = min(hit_7d/50,1)*100
    freshness = max(0,1-last_crawled_hours/48)*100
    topic = topic_score*100
    return 0.35*topic + 0.25*activity + 0.20*freshness + 0.10*(100*(1-spam_ratio)) + 0.10*(100*(1-dup_ratio))

def a_score(relevance, coverage, evidence_avg, median_days, dup_ratio, spam_ratio, diversity):
    evidence_strength = min(2, evidence_avg)/2*100
    freshness = max(0,1-median_days/7)*100
    cleanliness = 100*(1-dup_ratio)*(1-spam_ratio)
    return 0.30*relevance + 0.20*coverage + 0.20*evidence_strength + 0.15*freshness + 0.10*cleanliness + 0.05*diversity

19.3 CSV 模板（下载）
	•	社区抽检模板
	•	算法/报告抽检模板

⸻

20. Definition of Done（验收清单）
	•	反馈事件表与索引上线；
	•	5 个 Admin API + 1 个聚合接口可用；
	•	三页前端实现，包含筛选、排序、详情侧栏、操作按钮、Patch 预览下载；
	•	与任务系统“仅核心重跑”打通；
	•	前台反馈入库，Admin 汇总可见；
	•	8 条 E2E 用例通过；
	•	安全审计：非 Admin 拒绝；样例仅链接不含 PII；
	•	文档更新：阈值配置与分位数策略写入配置仓库。
