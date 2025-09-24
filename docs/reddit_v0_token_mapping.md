# Reddit V0 主题 Token 对照表

> 数据来源：`reddit_v0界面/styles/globals.css` 与 `frontend/src/styles/index.css`。
>
> 说明：设计版采用 OKLCH 表达色彩；当前前端使用 HSL。后续实现可选择直接迁移至 OKLCH，或在 Tailwind 变量中提供精确的 HSL 等效值。

| Token | reddit_v0界面 (OKLCH) | frontend 当前 (HSL) | 备注 |
| --- | --- | --- | --- |
| `--background` | `oklch(1 0 0)` | `0 0% 98%` | 设计版纯白背景，需评估是否沿用浅灰 (#fafafa)。 |
| `--foreground` | `oklch(0.145 0 0)` | `0 0% 15%` | 设计版更深（近黑），当前为 #262626；对比度接近，可按设计微调。 |
| `--card` | `oklch(1 0 0)` | `0 0% 100%` | 一致。 |
| `--card-foreground` | `oklch(0.145 0 0)` | `0 0% 15%` | 一致。 |
| `--popover` | `oklch(1 0 0)` | `0 0% 100%` | 一致。 |
| `--popover-foreground` | `oklch(0.145 0 0)` | `0 0% 15%` | 一致。 |
| `--primary` | `oklch(0.205 0 0)` | `0 0% 15%` | 设计版主色为深黑按钮，当前同值但颜色模型不同；落地时需确保与设计一致的亮度。 |
| `--primary-foreground` | `oklch(0.985 0 0)` | `0 0% 100%` | 一致。 |
| `--secondary` | `oklch(0.97 0 0)` | `243 100% 73%` | 设计版次要按钮是浅灰；当前实现使用紫色 (#7973FF)。需回归 UI 定义，决定以设计稿为准。 |
| `--secondary-foreground` | `oklch(0.205 0 0)` | `0 0% 100%` | 设计版用深色文字，现实现白字。随 secondary 色彩一起调整。 |
| `--muted` | `oklch(0.97 0 0)` | `0 0% 96%` | 设计版偏白，现实现略偏浅灰；影响表单背景和卡片填充。 |
| `--muted-foreground` | `oklch(0.556 0 0)` | `0 0% 30%` | 设计版偏中灰 (≈#6C6C6C)；现实现为更深灰，需调整。 |
| `--accent` | `oklch(0.97 0 0)` | `243 100% 73%` | 设计版 accent 与 secondary 相同（浅灰），现实现仍是紫色，用于 Hover/强调需重对齐。 |
| `--accent-foreground` | `oklch(0.205 0 0)` | `0 0% 100%` | 与 secondary foreground 问题相同。 |
| `--destructive` | `oklch(0.577 0.245 27.325)` | `346 77% 49%` | 设计版稍偏暗红 (#C23645 近似)，现实现为亮红 (#BE123C)。需换算。 |
| `--destructive-foreground` | `oklch(0.577 0.245 27.325)` | `0 0% 100%` | 设计稿采用同色文字（深红），现实现白色。需决定最终视觉。 |
| `--border` | `oklch(0.922 0 0)` | `0 0% 90%` | 设计版更浅，现实现稍深 (#E5E5E5)；以设计为准。 |
| `--input` | `oklch(0.922 0 0)` | `0 0% 100%` | 设计版接近浅灰，现实现纯白。 |
| `--ring` | `oklch(0.708 0 0)` | `243 100% 73%` | 设计版 focus ring 为中灰（≈#BCBCBC），现实现紫色。 |
| `--sidebar` | `oklch(0.985 0 0)` | `0 0% 99%` | 接近一致。 |
| `--sidebar-foreground` | `oklch(0.145 0 0)` | `0 0% 15%` | 一致。 |
| `--sidebar-primary` | `oklch(0.205 0 0)` | `243 100% 73%` | 设计版为深色，现实现紫色；需统一。 |
| `--sidebar-primary-foreground` | `oklch(0.985 0 0)` | `0 0% 100%` | 设计稿为白字，现实现一致。 |
| `--sidebar-accent` | `oklch(0.97 0 0)` | `328 86% 70%` | 设计版浅灰，现实现粉色；需统一。 |
| `--sidebar-accent-foreground` | `oklch(0.205 0 0)` | `0 0% 100%` | 设计版深色文字，现实现白字。 |
| `--sidebar-border` | `oklch(0.922 0 0)` | `0 0% 90%` | 设计版更浅。 |
| `--sidebar-ring` | `oklch(0.708 0 0)` | `262 83% 58%` | 设计版中灰 Focus，现实现深紫。 |
| `--radius` | `0.625rem` | `0.5rem` | 设计版更圆；需同步 `border-radius` 设置。 |
| `--radius-sm/md/lg/xl` | `var(--radius)` 基础下的 ±2/4 px | 当前自定义为 ±3/6px | 逐一调整以匹配设计。 |
| `--shadow-soft` | 未显式定义（通过 OKLCH 配套阴影） | `0 18px 45px rgba(15, 23, 42, 0.08)` | 设计稿需从 Figma 抓取或按组件阴影值替换。 |

> 夜间模式变量同理需更新，此处暂聚焦亮色模式；Phase 5 将统一处理暗色主题。

后续执行建议：
1. 将 OKLCH 转换为对应 HSL/HEX 或直接启用 Tailwind OKLCH 支持；
2. 更新 `src/styles/index.css` 与 Tailwind `extend.colors`，同步按钮、卡片、面包屑等组件样式；
3. 校准 `border-radius`、`box-shadow`、字体 weight，保证与设计稿截图对齐。
