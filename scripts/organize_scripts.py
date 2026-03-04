#!/usr/bin/env python3
"""
测试和调试脚本迁移工具

此脚本帮助整理根目录的测试和调试文件，将它们移动到合适的位置。
"""

import os
import shutil
from pathlib import Path

# 定义目录
ROOT_DIR = Path(__file__).parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
TESTS_DIR = ROOT_DIR / "tests"
FIXTURES_DIR = TESTS_DIR / "fixtures"

# 文件分类
DEBUG_SCRIPTS = [
    "debug_tools.py",
    "debug_voice.py",
    "diagnose_voice.py",
]

MODEL_SCRIPTS = [
    "download_model.py",
    "download_model2.py",
    "check_model.py",
    "check_model2.py",
    "fix_model.py",
    "test_model.py",
]

TEST_SCRIPTS = [
    "test_exec_tool.py",
    "test_imports.py",
    "test_modules.py",
    "test_run.py",
    "test_run2.py",
    "test_run3.py",
    "run_test.py",
    "simple_test.py",
    "quick_test_exec.py",
]

VOICE_SCRIPTS = [
    "run_voice.py",
    "test_voice.py" if (ROOT_DIR / "test_voice.py").exists() else None,
]

CONFIG_SCRIPTS = [
    "check_config.py",
    "check_deps.py",
]


def ensure_directories():
    """确保目标目录存在"""
    SCRIPTS_DIR.mkdir(exist_ok=True)
    FIXTURES_DIR.mkdir(exist_ok=True)
    (TESTS_DIR / "fixtures").mkdir(exist_ok=True)


def move_files(files, target_dir, category="scripts"):
    """移动文件到目标目录"""
    moved = []
    for filename in files:
        if filename is None:
            continue
        src = ROOT_DIR / filename
        if src.exists():
            dst = target_dir / filename
            shutil.move(str(src), str(dst))
            moved.append(filename)
            print(f"✓ 移动 {filename} -> {target_dir.name}/")
    return moved


def create_script_readme():
    """创建 scripts 目录的 README"""
    readme_content = """# Scripts 目录

此目录包含项目的辅助脚本和工具。

## 脚本分类

### 调试脚本
- `debug_tools.py` - 工具调试脚本
- `debug_voice.py` - 语音功能调试
- `diagnose_voice.py` - 语音问题诊断

### 模型相关
- `download_model.py` - 模型下载脚本
- `check_model.py` - 模型检查脚本
- `fix_model.py` - 模型修复脚本

### 测试工具
- `test_*.py` - 各类测试脚本
- `run_test.py` - 测试运行器

### 配置工具
- `check_config.py` - 配置检查
- `check_deps.py` - 依赖检查

## 使用方法

```bash
# 运行脚本
python scripts/debug_tools.py

# 或在项目根目录
python -m scripts.debug_tools
```

## 注意事项

- 这些脚本主要用于开发和调试
- 生产环境不需要这些脚本
- 部分脚本可能需要特定配置才能运行
"""
    readme_path = SCRIPTS_DIR / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"✓ 创建 {readme_path}")


def create_tests_readme():
    """创建 tests 目录的 README"""
    readme_content = """# Tests 目录

此目录包含项目的测试套件。

## 目录结构

```
tests/
├── fixtures/          # 测试夹具和辅助数据
├── voice/            # 语音功能测试
├── test_*.py         # 各类单元测试
└── README.md         # 本文档
```

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_web_channel.py -v

# 查看覆盖率
pytest --cov=kaolalabot tests/

# 运行语音相关测试
pytest tests/voice/ -v
```

## 测试规范

- 测试文件以 `test_` 开头
- 测试函数以 `test_` 开头
- 使用 pytest 框架
- 异步测试使用 pytest-asyncio

## 添加新测试

1. 在对应模块下创建测试文件
2. 导入必要的模块
3. 编写测试函数
4. 运行测试确保通过

## 测试夹具

`fixtures/` 目录包含测试所需的辅助数据和配置文件。
"""
    readme_path = TESTS_DIR / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"✓ 创建 {readme_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("开始整理测试和调试脚本...")
    print("=" * 60)
    
    # 确保目录存在
    ensure_directories()
    
    # 创建子目录
    debug_dir = SCRIPTS_DIR / "debug"
    debug_dir.mkdir(exist_ok=True)
    
    # 移动调试脚本
    print("\n📁 移动调试脚本...")
    move_files(DEBUG_SCRIPTS, debug_dir, "debug")
    
    # 移动模型相关脚本
    print("\n📁 移动模型相关脚本...")
    model_dir = SCRIPTS_DIR / "models"
    model_dir.mkdir(exist_ok=True)
    move_files(MODEL_SCRIPTS, model_dir, "models")
    
    # 移动测试脚本到 tests 目录
    print("\n📁 移动测试脚本...")
    move_files(TEST_SCRIPTS, TESTS_DIR / "legacy", "tests")
    
    # 移动语音相关脚本
    print("\n📁 移动语音相关脚本...")
    voice_dir = SCRIPTS_DIR / "voice"
    voice_dir.mkdir(exist_ok=True)
    move_files(VOICE_SCRIPTS, voice_dir, "voice")
    
    # 移动配置相关脚本
    print("\n📁 移动配置相关脚本...")
    tools_dir = SCRIPTS_DIR / "tools"
    tools_dir.mkdir(exist_ok=True)
    move_files(CONFIG_SCRIPTS, tools_dir, "tools")
    
    # 创建 README
    print("\n📝 创建 README 文件...")
    create_script_readme()
    create_tests_readme()
    
    print("\n" + "=" * 60)
    print("整理完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
