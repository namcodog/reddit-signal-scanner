# Reddit V0 页面布局与排版规格

> 目标：指导 `frontend` 工程实现与 `reddit_v0界面` 设计 100% 一致的视觉与交互。以下尺寸基于 Tailwind 默认配置（1rem = 16px）。

## 1. 全局框架
- **页面背景**：`bg-background`（设计版 OKLCH `0.0` → 纯白），`min-h-screen` 需占满视口。
- **主容器**：`container mx-auto px-4` → 最大宽度 1280px（Tailwind container 默认），左右内边距 1rem (16px)。
- **纵向节距**：主内容 `py-8`（32px），组件块间普遍使用 `space-y-8` (32px) 或 `space-y-4` (16px)。

## 2. 顶部导航（`app/page.tsx:63-91`）
| 元素 | 类名 | 数值/样式 |
| --- | --- | --- |
| 顶部栏 | `border-b border-border bg-card` | 底部描边 1px（颜色 `--border`），背景与卡片同色 |
| 内部容器 | `container mx-auto px-4 py-4 flex items-center justify-between` | 左右内边距 16px，上下 16px，行高 flex 对齐 |
| 品牌图标框 | `w-8 h-8 bg-primary rounded-lg flex` | 32×32px，圆角 12px（Tailwind `rounded-lg` ≈ 0.5rem）|
| 标题 | `text-xl font-bold` | 字号 1.25rem (20px)，字重 700 |
| 按钮组间距 | `space-x-4` | 水平间距 16px；按钮大小 `size="sm"` (`h-9`, `px-3.5`) |

## 3. 错误提示条（`app/page.tsx:95-101`）
- 容器：`mb-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg` → 外边距下 16px，内边距 16px，圆角 0.5rem，边框/背景颜色需与设计版一致。
- 文本：`text-sm` (14px)，颜色 `text-destructive`。

## 4. 面包屑导航（`components/navigation-breadcrumb.tsx`）
| 项目 | 类名 | 规格 |
| --- | --- | --- |
| 容器 | `flex items-center justify-center space-x-2 text-sm mb-8` | 文字 14px，底部外边距 32px |
| 步骤按钮 | `px-3 py-1 rounded-md` | 水平 12px，垂直 4px，圆角 0.375rem |
| 图标圆形底 | `flex size-8 items-center justify-center rounded-full bg-secondary/70` | 32×32px，背景半透明 secondary |
| 标题/描述 | `font-medium` + `text-xs opacity-75` | 标题 16px；描述 12px，透明度 75% |
| 分隔符 | `ChevronRight` 图标，尺寸 `w-4 h-4` (16px) |

## 5. 输入阶段 (`components/product-input-form.tsx`)
### 5.1 整体
- 外层：`max-w-4xl mx-auto space-y-8` → 最大宽度 56rem (896px)，居中，区块间距 32px。
- 顶部图标：`w-12 h-12 rounded-xl` → 48×48px，圆角 0.75rem。
- 标题：`text-3xl font-bold` → 1.875rem (30px)；副标题 `text-lg` (18px)，最大宽 `max-w-2xl` (32rem/512px)。

### 5.2 主卡片
| 元素 | 类名 | 参数 |
| --- | --- | --- |
| 卡片 | `border-2 border-dashed border-border hover:border-secondary/50` | 虚线边框 2px；默认色 `--border`
| 表单容器 | `space-y-6` | 区块间距 24px |
| 文本域 | `min-h-40 p-4 border rounded-lg bg-input` | 最小高 10rem (160px)，内边距 16px，圆角 0.5rem |
| 提示行 | `flex justify-between text-sm` | 字号 14px，颜色 `text-muted-foreground` |
| 按钮 | `w-full size=lg` | 高度 48px，字体 16px，图标 16px（`w-4 h-4`） |

### 5.3 示例卡片
- Grid：`grid grid-cols-1 md:grid-cols-3 gap-4` → 移动单列，≥768px 三列，列间距 16px。
- 卡片内边距：`CardHeader pb-2`, `CardContent` 默认 24px。
- Hover：`hover:shadow-md` + `hover:border-secondary/50`，需确保阴影与设计一致。

### 5.4 流程步骤
- 容器：`bg-card rounded-lg p-6 border border-border` → 内边距 24px，圆角 0.5rem。
- 内部 Grid：`md:grid-cols-3 gap-6` → 间距 24px，居中对齐元素。
- 图标圆：`w-12 h-12` (48px)，背景 `secondary/10`。

## 6. 分析阶段 (`components/analysis-progress.tsx`)
- 外层与输入页一致：`max-w-4xl mx-auto space-y-8`。
- 顶部登录按钮行：`flex justify-end mb-4` → 与右侧对齐。
- 进度卡片关键规格：
  - 主标题行：`CardHeader` 内 `flex flex-col gap-6 md:flex-row md:items-center md:justify-between`（设计稿, 需在现实现中复刻）。
  - 进度条：`Progress` 高度 0.75rem (12px)；圆角同 tailwind `rounded-full`。
  - 步骤列表：每项 `flex items-start gap-4 rounded-xl border p-4` → 左图标容器 `size-10` (40px) 圆角 9999px。
  - 实时统计卡：`grid grid-cols-1 sm:grid-cols-3 gap-4`, 卡片 `p-4 text-center`。
- 登录对话框：宽 `sm:max-w-md` (28rem/448px)，表单间距 `space-y-4`。

## 7. 报告阶段 (`components/insights-report.tsx`)
- 整体容器：同输入/分析 `max-w-4xl mx-auto space-y-8`。
- 顶部标题条：`flex flex-wrap items-center justify-between gap-4`，按钮 `Button variant="outline" size="sm"`。
- 统计面板：`grid grid-cols-1 md:grid-cols-4 gap-4`，卡片 `p-4 text-center`。
- Tabs：`TabsList` 使用 `grid w-full grid-cols-2 gap-2 p-1 md:grid-cols-4` → 标签高度 ~40px，圆角 0.5rem。
- 内容卡：
  - 市场情感卡：标题行 `flex items-center gap-2`，Progress 条高度 8px (`h-2`)。
  - 表格/列表区域使用 `space-y-4`。
- 反馈弹窗：`ReportEvaluationDialog` 需保持与设计版一致的标题、评分按钮尺寸（默认 Button `size="sm"`）。

## 8. 版式与字体
- 字体家族：`--font-sans` (设计版 Geist Sans)，需在 `frontend` 配置中切换或引入相同字体。
- 标题层级：`text-3xl` (30px) 主标题；`text-lg` (18px) 副标题；`text-sm` (14px) 提示；`text-xs` (12px) 描述。
- 行距：Tailwind 默认 `leading-6` (24px) 对应 `text-base`; 可通过 `leading-relaxed` (1.625) 实现设计稿的松散排版。

## 9. 间距参考速查
| Tailwind 类 | 对应像素 |
| --- | --- |
| `px-4` / `py-4` | 16px |
| `py-8` / `space-y-8` | 32px |
| `space-y-6` | 24px |
| `gap-4` | 16px |
| `gap-6` | 24px |
| `rounded-lg` | 8px |
| `rounded-xl` | 12px |
| `rounded-full` | 9999px |

## 10. 实施注意事项
1. **容器宽度**：所有主要内容必须限制在 `max-w-4xl` 以内，避免拉伸超过设计宽度。
2. **卡片阴影**：设计稿 hover 阴影 `shadow-md`（0 4px 6px, 0.1），静态卡片多为无阴影或轻量 `shadow-sm`。
3. **响应式断点**：`md` (768px) 为三列栅格、并排布局的开关点，需要精准复刻。
4. **Icon 大小**：统一使用 `w-5 h-5` (20px) 或 `w-6 h-6` (24px)；图标外容器与设计稿一致（32px/48px）。
5. **按钮尺寸**：`size="lg"` → 高 48px；`size="sm"` → 高 36px。需按照设计稿选择。
6. **文字颜色**：参照 `docs/reddit_v0_token_mapping.md`，确保次要文本使用 `text-muted-foreground`（设计版中灰）。

通过本规范，可逐项比对实现中的容器宽度、边距、圆角、字体、颜色，确保最终界面在每个元素级别上与 `reddit_v0界面` 一致。后续开发请在提交前逐项核对。
