# 四层测试金字塔策略

## 概述

Reddit Signal Scanner采用四层测试金字塔策略，确保代码质量和系统可靠性。

```
              验收测试 (2%)
           ┌─────────────────┐
          │  Cypress/E2E    │
         └─────────────────┘
            系统测试 (8%)
      ┌──────────────────────────┐
     │   端到端业务流程测试        │
    └──────────────────────────┘
         集成测试 (20%)
   ┌─────────────────────────────────┐
  │    API端点、数据库事务、组件集成    │
 └─────────────────────────────────┘
           单元测试 (70%)
┌──────────────────────────────────────────┐
│ 函数、类方法、纯逻辑、组件单元测试           │
└──────────────────────────────────────────┘
```

## 各层详细说明

### 1. 单元测试 (70%)

**目标**: 测试最小可测试单元，提供快速反馈

**特征**:
- 执行速度: < 100ms/测试
- 隔离度: 100% (无外部依赖)
- Mock策略: 全Mock外部依赖
- 并发执行: 支持

**使用装饰器**:
```python
@TestIsolation.unit_test
def test_function():
    pass
```

**示例文件**:
- `tests/unit/backend/services/test_keyword_processor_unit.py`

### 2. 集成测试 (20%)

**目标**: 验证组件间交互和接口契约

**特征**:
- 执行速度: < 1s/测试
- 隔离度: 部分Mock
- 环境切换: 支持Mock/Real模式
- 并发执行: 不推荐

**使用装饰器**:
```python
@TestIsolation.integration_test
def test_api_endpoint():
    pass
```

**示例文件**:
- `tests/integration/backend/api/test_analysis_endpoint_integration.py`

### 3. 系统测试 (8%)

**目标**: 端到端业务流程验证

**特征**:
- 执行速度: < 30s/测试
- 真实环境: 优先使用Real API
- 数据清理: 自动清理测试数据
- 并发执行: 不支持

**使用装饰器**:
```python
@TestIsolation.system_test
def test_complete_workflow():
    pass
```

**示例文件**:
- `tests/system/workflows/test_complete_analysis_workflow.py`

### 4. 验收测试 (2%)

**目标**: 用户视角的完整场景验证

**特征**:
- 执行速度: < 5min/测试
- 完全真实: 必须使用Real API
- 跨浏览器: Chrome, Firefox, Safari
- 并发执行: 不支持

**使用装饰器**:
```python
@TestIsolation.acceptance_test
def test_user_journey():
    pass
```

**示例文件**:
- `tests/acceptance/user_journeys/test_first_time_user_e2e.py`

## 测试策略原则

### 1. 故障优先 (Failure-First)

先测试异常情况，再测试正常情况：

```python
def test_invalid_input_first():
    # 1. 测试所有异常情况
    with pytest.raises(ValueError):
        process([])  # 空输入
    
    # 2. 最后测试正常情况
    result = process(["valid"])
    assert result == expected
```

### 2. 边界驱动 (Boundary-Driven)

重点测试边界条件：

```python
@pytest.mark.parametrize("input_size", [0, 1, 10, 100, 1000, 10000])
def test_boundaries(input_size):
    # 测试不同规模的输入
    pass
```

### 3. 并发安全 (Concurrency-Safe)

验证多线程/多用户环境下的安全性：

```python
async def test_concurrent_access():
    # 并发执行多个操作
    results = await asyncio.gather(*tasks)
    # 验证数据一致性
    assert_data_integrity(results)
```

## Mock/Real API切换

### 自动切换规则

```python
# 单元测试 - 始终Mock
@pytest.mark.unit
def test_unit(): pass  # 自动使用Mock

# 集成测试 - 可选切换
@pytest.mark.integration
def test_integration(): pass  # 默认Mock，可切换

# 系统测试 - 优先Real
@pytest.mark.system  
def test_system(): pass  # 优先Real，可回退Mock

# 验收测试 - 必须Real
@pytest.mark.acceptance
def test_acceptance(): pass  # 必须Real，否则跳过
```

### 手动控制

```python
# 强制使用Mock
@with_api_mode("mock")
def test_with_mock(): pass

# 强制使用Real
@with_api_mode("real")
def test_with_real(): pass
```

## 运行测试

### 按层运行

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 只运行系统测试
pytest -m system

# 只运行验收测试
pytest -m acceptance
```

### 按策略运行

```bash
# 故障优先测试
pytest -m failure_first

# 边界条件测试
pytest -m boundary_driven

# 并发安全测试
pytest -m concurrency_safe
```

### 完整测试套件

```bash
# 运行所有测试
pytest

# 运行所有测试并生成覆盖率报告
pytest --cov=backend/app --cov=frontend/src --cov-report=html

# 并行运行测试
pytest -n auto
```

## 质量指标

### 覆盖率目标

- 总体覆盖率: > 80%
- 单元测试贡献: ~60%
- 集成测试贡献: ~15%
- 系统测试贡献: ~4%
- 验收测试贡献: ~1%

### 性能目标

- 单元测试套件: < 2分钟
- 集成测试套件: < 5分钟
- 系统测试套件: < 10分钟
- 完整测试套件: < 15分钟

### 测试数量分布

基于1000个测试的理想分布：
- 单元测试: 700个
- 集成测试: 200个
- 系统测试: 80个
- 验收测试: 20个