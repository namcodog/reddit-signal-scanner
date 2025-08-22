# 🚀 RedditNavigator MVP

> "Talk is cheap. Show me the code." - Linus Torvalds

极简商业机会发现工具：从Reddit讨论中发现未被满足的商业需求。

## 🎯 核心功能

**400行代码搞定3件事**：
1. **采集** - 抓取Reddit创业相关讨论
2. **分析** - 识别痛点和商业机会
3. **展示** - Web界面显示Top 10机会

## ⚡ 5分钟启动

### 1. 配置Reddit API
```bash
# 1. 访问 https://www.reddit.com/prefs/apps
# 2. 创建"script"类型应用
# 3. 编辑config.yaml，填入client_id和client_secret
```

### 2. 一键启动
```bash
chmod +x start.sh
./start.sh
```

### 3. 访问界面
```
http://localhost:5000
```

## 📁 项目结构

```
RedditNavigator/
├── collector.py    # 100行：Reddit数据采集
├── analyzer.py     # 200行：商业机会分析  
├── server.py       # 100行：Web展示界面
├── config.yaml     # 配置文件
├── start.sh        # 一键启动脚本
├── requirements.txt # 依赖包（4个）
└── README.md       # 本文档
```

## 🛠️ 技术栈

- **Python 3.8+** - 简单可靠
- **praw** - Reddit API
- **Flask** - Web框架
- **SQLite** - 数据存储
- **YAML** - 配置管理

## 🎨 设计哲学

### Linus式原则
- ✅ **KISS**: 2个数据表，不是20个
- ✅ **YAGNI**: 400行代码，不是4000行  
- ✅ **实用主义**: 先让它工作，再让它完美
- ✅ **好品味**: 消除特殊情况，统一处理逻辑

### 明确不做
- ❌ 用户系统
- ❌ 权限管理  
- ❌ 复杂报告
- ❌ 移动端APP
- ❌ API服务

## 📊 数据库设计

**仅2个表**：
- `posts` - 原始Reddit数据
- `analysis` - 分析结果

## 🧪 性能指标

- 采集100个帖子 < 60秒
- 分析100个帖子 < 30秒  
- 页面响应时间 < 2秒
- 内存使用 < 100MB

## 🚨 故障排除

### Reddit API限流
```yaml
# config.yaml 增加延迟
collection:
  request_delay_seconds: 3
```

### 依赖包问题
```bash
pip3 install praw flask pyyaml requests
```

### 数据库锁定
```bash
# 删除数据库文件重新初始化
rm reddit.db
python3 collector.py
```

## 🎯 4周开发计划

- **Week 1**: 基础功能（✅ 完成）
- **Week 2**: 用户验证
- **Week 3**: 产品优化  
- **Week 4**: 商业验证

## 📞 联系方式

- 项目问题：提交GitHub Issue
- Reddit API：https://reddit.com/dev/api
- Flask文档：https://flask.palletsprojects.com/

---

**记住Linus的名言**: "Talk is cheap. Show me the code."

**现在就开始使用，寻找你的商业机会！** 💡