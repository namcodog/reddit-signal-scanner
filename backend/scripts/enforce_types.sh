#!/bin/bash
# Reddit Signal Scanner - 零容忍类型检查脚本
# 基于Linus原则："发现问题立即修复，不允许逃避"

set -e

echo "🔍 Claude Code 严格类型检查开始..."
echo "================================="

# 检查是否传入文件参数
if [ $# -eq 0 ]; then
    echo "⚠️  用法: $0 <file1> [file2] ..."
    echo "示例: $0 app/services/analysis_engine.py"
    exit 1
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否有type: ignore使用
echo "📋 第1步：检查 type: ignore 使用..."
IGNORE_COUNT=0
for file in "$@"; do
    if [ -f "$file" ]; then
        count=$(grep -c "# type: ignore" "$file" 2>/dev/null || true)
        if [ "$count" -gt 0 ]; then
            echo -e "${RED}❌ 发现 $count 个 'type: ignore' 在 $file${NC}"
            echo "   违反Linus原则：这是设计问题的症状，请修复数据结构定义！"
            grep -n "# type: ignore" "$file"
            IGNORE_COUNT=$((IGNORE_COUNT + count))
        fi
    fi
done

if [ "$IGNORE_COUNT" -gt 0 ]; then
    echo -e "${RED}❌ 总计发现 $IGNORE_COUNT 个 type: ignore${NC}"
    echo "请先修复这些类型逃避问题再继续开发！"
    exit 1
else
    echo -e "${GREEN}✅ 未发现 type: ignore 使用${NC}"
fi

# 运行严格MyPy检查
echo ""
echo "📋 第2步：运行 MyPy 严格类型检查..."
echo "命令: mypy --strict --show-error-codes $@"
echo ""

# 执行MyPy检查
if mypy --strict --show-error-codes "$@"; then
    echo ""
    echo -e "${GREEN}✅ MyPy 严格检查通过！${NC}"
else
    echo ""
    echo -e "${RED}❌ MyPy 检查失败！${NC}"
    echo ""
    echo "💡 常见修复建议："
    echo "1. 所有函数必须有返回类型注解"
    echo "2. 所有参数必须有类型注解"  
    echo "3. 使用具体类型而不是Any"
    echo "4. 从数据结构设计层面解决问题"
    echo ""
    echo "请修复所有类型错误后再继续开发！"
    exit 1
fi

# 检查类型覆盖率
echo ""
echo "📋 第3步：检查类型注解覆盖率..."
for file in "$@"; do
    if [ -f "$file" ]; then
        # 统计函数定义
        func_count=$(grep -c "^def \|^async def " "$file" 2>/dev/null || true)
        # 统计带类型注解的函数
        typed_count=$(grep -c "^def .*->.*:\|^async def .*->.*:" "$file" 2>/dev/null || true)
        
        if [ "$func_count" -gt 0 ]; then
            coverage=$((typed_count * 100 / func_count))
            if [ "$coverage" -lt 100 ]; then
                echo -e "${YELLOW}⚠️  $file: 类型覆盖率 $coverage% ($typed_count/$func_count 函数有类型)${NC}"
            else
                echo -e "${GREEN}✅ $file: 类型覆盖率 100%${NC}"
            fi
        fi
    fi
done

echo ""
echo "================================="
echo -e "${GREEN}🎉 类型检查完成 - 代码符合Claude Code标准！${NC}"
echo ""
echo "📝 下一步建议："
echo "1. 运行代码格式化: black $@ && isort $@"
echo "2. 运行代码规范检查: flake8 $@ --max-line-length=88"
echo "3. 运行完整质量检查: python scripts/quality_gate.py --files $@"