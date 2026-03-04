# 贡献指南 (Contributing to kaolalabot)

首先，感谢您考虑为 kaolalabot 做出贡献！我们欢迎各种形式的贡献，包括代码、文档、问题报告和功能建议。

## 🤝 行为准则

本项目采用《贡献者公约》作为行为准则。请阅读并遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 中的规定。

## 📋 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议，请创建一个新的 issue：

1. 首先检查是否已有相关的 issue
2. 使用清晰的标题和描述
3. 提供复现步骤（对于 bug）
4. 说明您的环境信息（Python 版本、操作系统等）
5. 如果可能，提供最小复现代码

### 提交代码

#### 1. Fork 项目

在 GitHub 上 Fork 本项目到您的账户。

#### 2. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/kaolalabot.git
cd kaolalabot
```

#### 3. 创建开发环境

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -r requirements-backend.txt
pip install -e ".[dev]"
```

#### 4. 创建分支

```bash
# 保持 main 分支稳定，所有开发在新分支进行
git checkout -b feature/amazing-feature
```

分支命名规范：
- `feature/xxx` - 新功能
- `fix/xxx` - Bug 修复
- `docs/xxx` - 文档更新
- `refactor/xxx` - 代码重构
- `test/xxx` - 测试相关

#### 5. 开发规范

##### 代码风格

我们使用以下工具保证代码质量：

```bash
# 代码格式化
ruff format .

# 代码检查
ruff check .

# 类型检查
mypy kaolalabot/
```

##### 代码规范

- 遵循 PEP 8 风格指南
- 使用类型注解
- 函数和类必须有文档字符串
- 变量和函数命名清晰有意义
- 保持函数简洁（建议不超过 50 行）

##### 提交信息规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

Type 类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

示例：
```
feat(agent): 添加新的网络搜索工具

- 实现 web_search 工具
- 支持 DuckDuckGo 搜索
- 添加最大结果数限制

Closes #123
```

#### 6. 编写测试

```bash
# 运行测试套件
pytest tests/

# 运行特定测试
pytest tests/test_web_channel.py -v

# 查看测试覆盖率
pytest --cov=kaolalabot tests/
```

测试规范：
- 所有新功能必须包含测试
- 测试应独立且可重复
- 使用描述性的测试函数名
- 遵循 AAA 模式（Arrange-Act-Assert）

#### 7. 提交更改

```bash
git add .
git commit -m "feat: 添加新功能"
```

#### 8. 推送到远程

```bash
git push origin feature/amazing-feature
```

#### 9. 创建 Pull Request

1. 在 GitHub 上访问您的 fork
2. 点击 "Compare & pull request"
3. 填写 PR 描述：
   - 清晰的标题
   - 详细描述更改内容
   - 关联的 issue（如有）
   - 测试说明
4. 等待代码审查

### 代码审查流程

1. **自动检查**：CI 会自动运行测试和代码检查
2. **维护者审查**：至少需要一位维护者批准
3. **修改反馈**：根据审查意见进行修改
4. **合并**：审查通过后合并到 main 分支

### 文档贡献

- 更新 README.md 中的相关章节
- 为新增功能添加使用示例
- 更新 API 文档
- 添加必要的注释

## 📚 开发资源

- [项目架构文档](docs/design-guide.md)
- [API 文档](docs/api-reference.md)
- [示例代码](examples/)

## 💬 讨论与交流

- GitHub Issues: 功能请求和问题报告
- GitHub Discussions: 一般性讨论
- Email: kaolalabot@example.com

## 🎓 学习资源

kaolalabot 不仅是一个工具，也是一个学习资源。我们鼓励：

- 阅读源代码学习架构设计
- 通过示例代码理解最佳实践
- 参与社区讨论提升技能
- 分享您的使用经验和学习心得

## ⚖️ 许可证

通过贡献代码，您同意您的贡献遵循本项目的 MIT 许可证。

---

再次感谢您的贡献！🎉
