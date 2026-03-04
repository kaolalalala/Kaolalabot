# Tests 测试套件

此目录包含 kaolalabot 项目的完整测试套件。

## 📁 目录结构

```
tests/
├── fixtures/          # 测试夹具和辅助数据
├── voice/            # 语音功能专项测试
├── legacy/           # 旧版测试脚本（待重构）
├── test_*.py         # 单元测试和集成测试
└── README.md         # 本文档
```

## 🚀 运行测试

### 基础命令

```bash
# 运行所有测试
pytest tests/

# 运行所有测试（详细输出）
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_web_channel.py -v

# 运行特定测试函数
pytest tests/test_web_channel.py::test_channel_start -v
```

### 高级选项

```bash
# 查看测试覆盖率
pytest --cov=kaolalabot tests/

# 生成覆盖率报告（HTML）
pytest --cov=kaolalabot --cov-report=html tests/

# 运行标记的测试
pytest -m slow tests/

# 失败后停止
pytest -x tests/

# 重新运行失败的测试
pytest --lf tests/

# 并行运行测试（需要 pytest-xdist）
pytest -n auto tests/
```

### 语音测试

```bash
# 运行所有语音测试
pytest tests/voice/ -v

# 运行特定语音测试
pytest tests/voice/test_e2e.py -v
```

## 📝 测试分类

### 单元测试 (Unit Tests)
测试单个函数或类的行为。

- 文件名：`test_*.py`
- 位置：直接在 `tests/` 根目录
- 特点：快速、独立、无外部依赖

### 集成测试 (Integration Tests)
测试多个模块之间的交互。

- 文件名：`test_*_integration.py` 或在集成测试目录
- 特点：测试模块间通信和接口

### 端到端测试 (E2E Tests)
测试完整的用户流程。

- 位置：`tests/voice/test_e2e.py`
- 特点：模拟真实使用场景

### 性能测试 (Performance Tests)
测试代码的性能指标。

- 位置：`tests/voice/test_performance.py`
- 特点：测量响应时间、内存使用等

### 功能测试 (Functional Tests)
测试特定功能的正确性。

- 位置：`tests/voice/test_functional.py`
- 特点：验证功能需求

## 🧪 编写测试

### 测试模板

```python
"""
测试模块名称 - 简要描述
"""
import pytest
from kaolalabot import SomeClass

class TestSomeClass:
    """测试 SomeClass 类"""
    
    def test_initialization(self):
        """测试初始化"""
        obj = SomeClass()
        assert obj is not None
    
    def test_some_method(self):
        """测试某个方法"""
        obj = SomeClass()
        result = obj.some_method()
        assert result == expected_value

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await some_async_function()
    assert result is not None
```

### 测试夹具 (Fixtures)

在 `tests/fixtures/` 或测试文件中定义：

```python
import pytest

@pytest.fixture
def sample_config():
    """提供示例配置"""
    return {
        "key": "value",
        "enabled": True
    }

@pytest.fixture
def mock_llm_provider():
    """模拟 LLM 提供商"""
    class MockProvider:
        async def generate(self, prompt):
            return "Mock response"
    return MockProvider()

# 在测试中使用
def test_with_fixture(sample_config):
    assert sample_config["enabled"] is True
```

### 参数化测试

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert input * 2 == expected
```

## 📊 测试覆盖率

### 查看覆盖率

```bash
# 终端报告
pytest --cov=kaolalabot --cov-report=term-missing tests/

# HTML 报告（推荐）
pytest --cov=kaolalabot --cov-report=html tests/
# 然后打开 htmlcov/index.html
```

### 覆盖率目标

- 核心模块：> 80%
- 工具模块：> 70%
- 集成代码：> 60%

## 🔍 调试测试

### 使用 pdb 调试

```bash
# 在测试中设置断点
pytest --pdb tests/test_something.py

# 或在代码中
import pdb; pdb.set_trace()
```

### 详细输出

```bash
# 显示 print 输出
pytest -s tests/

# 显示本地变量
pytest -l tests/

# 显示最慢的 10 个测试
pytest --durations=10 tests/
```

## 🎯 测试最佳实践

### 1. 测试命名

- 使用描述性的函数名
- 遵循 `test_<功能>_<场景>_<预期>` 模式
- 示例：`test_web_search_with_invalid_query_returns_empty()`

### 2. AAA 模式

```python
def test_example():
    # Arrange - 准备
    obj = SomeClass()
    
    # Act - 执行
    result = obj.do_something()
    
    # Assert - 断言
    assert result == expected
```

### 3. 测试隔离

- 每个测试应该独立
- 使用 fixture 设置和清理
- 避免测试间的依赖

### 4. 测试数据

- 使用小的、有代表性的数据集
- 在 `fixtures/` 目录存放测试数据
- 避免依赖外部资源

## 📚 相关资源

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [pytest-cov](https://github.com/pytest-dev/pytest-cov)

## 🐛 常见问题

### Q: 测试导入错误

**A**: 确保在项目根目录运行 pytest，或安装开发版本：
```bash
pip install -e ".[dev]"
```

### Q: 异步测试失败

**A**: 确保添加 `@pytest.mark.asyncio` 装饰器，并安装 pytest-asyncio。

### Q: 测试运行缓慢

**A**: 
- 使用 `-n auto` 并行运行
- 标记慢速测试：`@pytest.mark.slow`
- 使用 `--durations` 找出瓶颈

---

**最后更新**: 2026-03-04
