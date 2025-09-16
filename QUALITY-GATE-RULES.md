# 🛡️ 质量门禁要求 - 编码前必读

> **目的**: 在编写代码前了解所有质量要求，避免提交时大量报错

## 🎯 **核心原则**
- **100%类型安全** - 禁止any类型和类型逃避
- **提交时强制检查** - 不符合要求的代码无法提交
- **前后端统一标准** - 同样严格的质量要求

---

## 🐍 **后端Python要求** (backend/app/*.py)

### ✅ **必须遵守**
```python
# 1. 所有函数必须有完整类型注解
def process_data(input_data: str, config: Config) -> ProcessResult:
    return ProcessResult()

# 2. 禁止使用 Dict[str, Any]
❌ data: Dict[str, Any] = {}
✅ data: Dict[str, str] = {}
✅ 或使用 TypedDict/Pydantic模型

# 3. 禁止使用 Any 类型  
❌ result: Any = get_data()
✅ result: ProcessResult = get_data()

# 4. 变量必须有类型注解（复杂情况）
❌ config = load_config()
✅ config: AppConfig = load_config()
```

### 📊 **当前技术债务**
- MyPy错误: 548个 (需逐步修复)
- Dict[str, Any]: 35个 (禁止新增)
- 无类型函数: 26个 (禁止新增)

---

## ⚛️ **前端TypeScript要求** (frontend/src/*.ts, *.tsx)

### ✅ **必须遵守**
```typescript
// 1. 禁止使用 any 类型
❌ const data: any = fetchData();
✅ const data: UserData = fetchData();

// 2. 函数参数必须有类型注解
❌ function processUser(user) { }
✅ function processUser(user: User): void { }

// 3. 组件Props必须定义接口
❌ function Button({ onClick, children }) { }
✅ interface ButtonProps {
     onClick: () => void;
     children: React.ReactNode;
   }
   function Button({ onClick, children }: ButtonProps) { }

// 4. 使用具体类型，避免泛型逃避
❌ const items: Record<string, any> = {};
✅ const items: Record<string, UserItem> = {};
```

### 🧪 **测试文件特殊规则** (*.test.ts, *.test.tsx)
```typescript
// 测试文件允许使用any，但仅限Mock
✅ const mockFn: any = vi.fn();  // Mock函数可以用any
✅ vi.mock('module', () => ({ default: vi.fn() as any }));

❌ const testData: any = { id: 1 };  // 测试数据不能用any
✅ const testData: TestData = { id: 1 };
```

---

## 🔧 **开发时快速检查命令**

### 实时质量检查
```bash
# 检查所有质量指标
make tech-debt-metrics

# 快速全栈质量检查  
make quality-check-full

# 只检查后端类型
make type-check

# 只检查前端类型
cd frontend && npm run type-check

# 只检查前端代码规范
cd frontend && npm run lint
```

### 提交前验证
```bash
# 模拟pre-commit检查
pre-commit run --all-files

# 或者只检查暂存的文件
git add . && pre-commit run
```

---

## 🚨 **常见错误避免指南**

### 后端常见错误
```python
# ❌ 常见错误1: 缺少返回类型
def get_user_data(id: int):  # 缺少返回类型
    return {"name": "test"}

# ✅ 正确写法
def get_user_data(id: int) -> Dict[str, str]:
    return {"name": "test"}

# ❌ 常见错误2: 使用Any字典
def process_config() -> Dict[str, Any]:  # 被门禁阻止
    return {}

# ✅ 正确写法  
class ConfigData(TypedDict):
    name: str
    value: int
    
def process_config() -> ConfigData:
    return {"name": "test", "value": 1}
```

### 前端常见错误
```typescript
// ❌ 常见错误1: 隐式any参数
const handleClick = (event) => {  // event是any类型
  console.log(event);
};

// ✅ 正确写法
const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
  console.log(event);
};

// ❌ 常见错误2: any类型状态
const [data, setData] = useState<any>(null);

// ✅ 正确写法
interface UserData {
  id: number;
  name: string;
}
const [data, setData] = useState<UserData | null>(null);
```

---

## 🎯 **编码前检查清单**

在开始编写代码前，确认：

### 后端Python
- [ ] 知道函数的输入输出类型
- [ ] 准备好使用TypedDict或Pydantic代替Dict[str, Any]
- [ ] 了解业务对象的数据结构

### 前端TypeScript  
- [ ] 定义好组件的Props接口
- [ ] 确定状态数据的类型结构
- [ ] 准备好API调用的返回类型定义

### 通用
- [ ] 运行 `make tech-debt-metrics` 了解当前状态
- [ ] 有疑问时先运行类型检查，而不是等到提交

---

## 💡 **快速修复技巧**

遇到类型错误时：

1. **先运行检查**：`make quality-check-full`
2. **看具体错误**：错误信息会指出具体问题
3. **使用IDE提示**：VSCode/WebStorm会提供类型建议
4. **参考现有代码**：寻找相似功能的正确实现

---

**记住**: 质量门禁是帮助我们写出更好代码的工具，不是障碍！

提交前运行 `git add . && pre-commit run` 可以提前发现所有问题。