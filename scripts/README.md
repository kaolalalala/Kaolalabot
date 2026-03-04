# Scripts 目录

此目录包含项目的辅助脚本和工具，主要用于开发、调试和维护。

## 📁 目录结构

```
scripts/
├── debug/           # 调试脚本
├── models/          # 模型相关脚本
├── voice/           # 语音功能脚本
├── tools/           # 工具脚本
├── organize_scripts.py  # 脚本整理工具
└── README.md        # 本文档
```

## 🔧 脚本分类

### 调试脚本
- `debug_tools.py` - 工具调试脚本，用于测试和调试各种工具
- `debug_voice.py` - 语音功能调试，测试语音输入输出
- `diagnose_voice.py` - 语音问题诊断，帮助排查语音功能问题

### 模型相关脚本
- `download_model.py` - 模型下载脚本，下载所需的 AI 模型
- `download_model2.py` - 备用模型下载脚本
- `check_model.py` - 模型检查脚本，验证模型是否正确安装
- `check_model2.py` - 备用模型检查脚本
- `fix_model.py` - 模型修复脚本，修复模型相关问题
- `test_model.py` - 模型测试脚本

### 语音功能脚本
- `run_voice.py` - 语音功能运行脚本

### 工具脚本
- `check_config.py` - 配置检查工具，验证配置文件是否正确
- `check_deps.py` - 依赖检查工具，检查项目依赖是否完整

## 📖 使用方法

### 运行脚本

```bash
# 从项目根目录运行
python scripts/check_config.py

# 或使用模块方式
python -m scripts.check_config

# 运行特定类别的脚本
python scripts/debug/debug_tools.py
python scripts/models/check_model.py
```

### 脚本整理工具

如果根目录出现了新的测试或调试脚本，可以运行整理工具：

```bash
python scripts/organize_scripts.py
```

这将自动识别并移动脚本到合适的子目录。

## ⚠️ 注意事项

1. **开发环境专用**：这些脚本主要用于开发和调试，生产环境通常不需要
2. **配置依赖**：部分脚本可能需要特定的配置文件或环境变量
3. **Python 版本**：确保使用 Python 3.11+ 运行这些脚本
4. **依赖安装**：运行前确保已安装项目依赖：`pip install -r requirements-backend.txt`

## 🎯 最佳实践

### 创建新脚本

如果您需要添加新的调试或工具脚本：

1. 在合适的子目录下创建文件
2. 添加清晰的文档字符串说明用途
3. 使用 `if __name__ == "__main__":` 保护主逻辑
4. 提供必要的错误处理和日志输出

### 脚本模板

```python
#!/usr/bin/env python3
"""
脚本名称 - 简要描述脚本功能

使用方法:
    python scripts/category/script_name.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

def main():
    """主函数"""
    # 实现脚本逻辑
    pass

if __name__ == "__main__":
    main()
```

## 📚 相关文档

- [测试文档](../tests/README.md) - 了解测试套件的使用
- [贡献指南](../CONTRIBUTING.md) - 代码贡献规范
- [项目设计指南](../docs/design-guide.md) - 项目架构说明

---

**最后更新**: 2026-03-04
