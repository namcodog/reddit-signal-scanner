import React, { useEffect, useMemo, useState } from 'react';
import { Lightbulb, Target, Zap, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

interface ProductInputFormProps {
  onStartAnalysis: (description: string) => Promise<void> | void;
  submitting?: boolean;
  value?: string;
  onChange?: (nextValue: string) => void;
  minLength?: number;
  maxLength?: number;
}

const exampleIdeas = [
  {
    title: 'SaaS 工具',
    description: '一个面向远程团队的项目管理工具，集成 Slack 并自动跟踪任务时间...'
  },
  {
    title: '移动应用',
    description: '一个健身应用，根据可用设备和时间限制创建个性化锻炼计划...'
  },
  {
    title: '电商平台',
    description: '一个专注于可持续时尚品牌的在线市场，重视透明度和道德制造...'
  },
] as const;

const DEFAULT_MIN_LENGTH = 10;
const DEFAULT_MAX_LENGTH = 2000;

const ProductInputForm: React.FC<ProductInputFormProps> = ({
  onStartAnalysis,
  submitting = false,
  value,
  onChange,
  minLength = DEFAULT_MIN_LENGTH,
  maxLength = DEFAULT_MAX_LENGTH,
}) => {
  const [description, setDescription] = useState(value ?? '');

  useEffect(() => {
    setDescription(value ?? '');
  }, [value]);

  const { charCount, isValid, helperText } = useMemo(() => {
    const length = description.length;
    const withinRange = length >= minLength && length <= maxLength;

    let message = '字数适合分析';
    if (length < minLength) {
      message = `还需要至少 ${minLength - length} 个字`;
    }
    if (length > maxLength) {
      message = `超出 ${length - maxLength} 个字`;
    }

    return { charCount: length, isValid: withinRange, helperText: message };
  }, [description, maxLength, minLength]);

  const updateDescription = (nextValue: string) => {
    setDescription(nextValue);
    onChange?.(nextValue);
  };

  const handleTextareaChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateDescription(event.target.value);
  };

  const handleExampleSelect = (value: string) => {
    updateDescription(value);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = description.trim();
    if (!trimmed || !isValid || submitting) {
      return;
    }
    await onStartAnalysis(trimmed);
  };

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8">
      <div className="space-y-4 text-center">
        <div className="mb-4 flex items-center justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-secondary/10 text-secondary">
            <Lightbulb className="h-6 w-6" />
          </div>
        </div>
        <h2 className="text-3xl font-bold text-foreground">描述您的产品想法</h2>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          详细告诉我们您的产品或服务。您描述得越具体，我们能提供的洞察就越好。
        </p>
      </div>

      <Card className="border-2 border-dashed border-border transition-colors hover:border-secondary/50">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Target className="h-5 w-5 text-secondary" />
                <span>产品描述</span>
              </CardTitle>
              <CardDescription>包括您的目标受众、核心功能以及您要解决的问题</CardDescription>
            </div>
            <Badge variant={isValid ? 'default' : 'secondary'} className="rounded-full px-3 py-1">
              {charCount} 字
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="product-description" className="sr-only">
                产品描述
              </Label>
              <textarea
                id="product-description"
                value={description}
                onChange={handleTextareaChange}
                maxLength={maxLength}
                className="min-h-40 w-full resize-none rounded-lg border border-border bg-input p-4 text-base text-foreground shadow-sm transition-all placeholder:text-muted-foreground focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="示例：一个帮助忙碌专业人士进行餐食准备的移动应用，根据饮食偏好、烹饪时间限制和当地杂货店供应情况生成个性化的每周餐食计划。该应用包括自动生成购物清单、分步烹饪指导以及与热门配送服务集成等功能..."
              />
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                <span>{helperText}</span>
                <span>建议 {minLength}-{maxLength} 字</span>
              </div>
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={!isValid || submitting}>
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="size-4 animate-spin rounded-full border-2 border-background border-t-transparent" />
                  正在提交
                </span>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  开始 5 分钟分析
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h3 className="text-center text-lg font-semibold text-foreground">需要灵感？试试这些示例：</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {exampleIdeas.map((example) => (
            <Card
              key={example.title}
              role="button"
              tabIndex={0}
              className="cursor-pointer border border-border transition-all hover:border-secondary/50 hover:shadow-md focus-visible:border-secondary focus-visible:ring-2 focus-visible:ring-secondary/40"
              onClick={() => handleExampleSelect(example.description)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  handleExampleSelect(example.description);
                }
              }}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-secondary">{example.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground line-clamp-3">{example.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="mb-4 text-center text-lg font-semibold text-foreground">接下来会发生什么？</h3>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div className="space-y-2 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary/10 text-secondary">
              <Clock className="h-6 w-6" />
            </div>
            <h4 className="font-medium text-foreground">步骤 1：分析</h4>
            <p className="text-sm text-muted-foreground">我们扫描相关的 Reddit 社区，寻找关于您市场的讨论</p>
          </div>
          <div className="space-y-2 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary/10 text-secondary">
              <Target className="h-6 w-6" />
            </div>
            <h4 className="font-medium text-foreground">步骤 2：处理</h4>
            <p className="text-sm text-muted-foreground">AI 分析用户痛点、竞品提及和市场机会</p>
          </div>
          <div className="space-y-2 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary/10 text-secondary">
              <Lightbulb className="h-6 w-6" />
            </div>
            <h4 className="font-medium text-foreground">步骤 3：洞察</h4>
            <p className="text-sm text-muted-foreground">获得包含可操作商业洞察的综合报告</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProductInputForm;
