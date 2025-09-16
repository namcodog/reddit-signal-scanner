# Reddit Signal Scanner 测试框架

基于四层测试金字塔的现代测试框架，支持Mock/Real环境切换。

## 快速开始

### 1. 验证测试框架

```bash
# 验证框架设置
make test-framework-verify

# 运行框架自检
make test-framework-check
```

### 2. 运行测试

```bash
# 按层运行
pytest -m unit          # 单元测试 (70%)
pytest -m integration   # 集成测试 (20%)
pytest -m system        # 系统测试 (8%)
pytest -m acceptance    # 验收测试 (2%)

# 运行所有测试
pytest

# 生成覆盖率报告
pytest --cov=backend/app --cov-report=html
```

## 编写测试

### 单元测试示例

```python
from tests.fixtures.base_fixtures import TestIsolation

@TestIsolation.unit_test
class TestKeywordProcessor:
    def test_empty_keywords_raises_error(self):
        """故障优先 - 先测试异常情况"""
        processor = KeywordProcessor()
        
        with pytest.raises(ValueError):
            processor.process_keywords([])
```

### 集成测试示例

```python
@TestIsolation.integration_test
class TestAnalysisEndpoint:
    async def test_create_task(self, authenticated_client):
        """测试API端点集成"""
        response = await authenticated_client.post(
            "/api/v1/discovery/analyze",
            json={"keywords": ["test"], "limit": 50}
        )
        assert response.status_code == 201
```

### Mock/Real切换

```python
# 自动切换（根据测试层级）
@pytest.mark.unit  # 自动使用Mock

# 手动控制
@with_api_mode("mock")
def test_with_mock(): pass

@with_api_mode("real")
def test_with_real(): pass
```

## 目录结构

```
tests/
├── strategy/         # 测试策略文档
├── config/          # 测试配置文件
├── fixtures/        # 测试fixtures和Mock服务
├── utils/           # 测试工具（API切换器等）
├── unit/            # 单元测试
├── integration/     # 集成测试
├── system/          # 系统测试
└── acceptance/      # 验收测试(E2E)
```

## 核心特性

1. **四层测试金字塔** - 70%单元/20%集成/8%系统/2%验收
2. **Mock/Real切换** - 灵活的环境切换机制
3. **类型安全** - 100%类型注解，禁止Any类型
4. **故障优先策略** - 先测试异常，后测试正常
5. **性能监控** - 内置性能计时器

## 质量指标

- 代码覆盖率目标: >80%
- 单元测试执行: <100ms/测试
- 完整测试套件: <15分钟
- MyPy严格模式: 零容忍

详细文档请参考 `tests/strategy/test_pyramid.md`