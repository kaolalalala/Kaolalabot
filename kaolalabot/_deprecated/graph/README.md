# Graph Runtime - LangGraph风格的执行框架

> Kaolalabot 的深度思考模式核心组件

## 概述

Graph Runtime 是一个基于 LangGraph 思想设计的任务执行框架，为 kaolalabot 提供：

- **长任务分步执行**：将复杂任务拆分为可管理的子任务
- **状态持久化**：支持检查点保存和恢复
- **错误恢复**：自动分类错误并执行相应恢复策略
- **人工介入**：支持暂停任务等待人工处理

## 核心概念

### 1. State（状态）

统一的全局状态对象，包含：
- `task_id`: 任务唯一标识
- `goal`: 用户目标
- `plan`: 子任务列表
- `node_history`: 节点执行历史
- `errors`: 错误记录
- `status`: 任务状态

### 2. Node（节点）

执行单元，包括：
- **planner**: 规划子任务
- **executor**: 执行子任务
- **verifier**: 验证结果
- **diagnoser**: 错误分类
- **recovery**: 恢复策略
- **summarizer**: 上下文压缩
- **human_gate**: 人工审核
- **finalizer**: 结果汇总

### 3. Edge（边）

条件路由：
- 固定跳转
- 条件跳转
- 循环
- 熔断

### 4. Checkpoint（检查点）

持久化执行状态，支持：
- 从最新检查点恢复
- 从指定检查点恢复
- 状态检查

## 使用方式

```python
from kaolalabot.graph import GraphRuntime, create_default_graph

# 创建运行时
nodes = create_default_graph(llm_provider=llm_provider)
runtime = GraphRuntime(nodes=nodes, max_steps=50)

# 执行任务
state = await runtime.run("复杂任务描述")
```

## 深度思考模式

在飞书中发送以下命令：

| 命令 | 功能 |
|------|------|
| `/deep on` | 开启深度思考模式 |
| `/deep off` | 关闭深度思考模式 |
| `/deep status` | 查看当前状态 |

## 错误处理

系统自动分类以下错误类型：

- **transient**: 瞬时错误（超时、网络抖动）
- **validation**: 验证失败
- **environment**: 环境变化
- **reasoning**: 规划错误
- **resource**: 资源限制
- **loop**: 重复循环

## 检查点

检查点存储在 `workspace/graph_checkpoints/` 目录。

查看任务状态：
```python
from kaolalabot.graph import Checkpointer

checkpointer = Checkpointer()
info = checkpointer.get_latest_checkpoint_info(task_id)
```

从检查点恢复：
```python
state = checkpointer.resume_from_latest(task_id)
```

## 文件结构

```
graph/
├── state.py          # 状态定义
├── nodes/
│   ├── base.py      # 节点基类
│   ├── planner.py   # 规划节点
│   ├── executor.py  # 执行节点
│   ├── verifier.py  # 验证节点
│   ├── diagnoser.py # 诊断节点
│   └── finalizer.py # 终节点
├── edges.py         # 路由机制
├── checkpoint.py    # 检查点存储
├── runtime.py      # 核心执行器
└── demo.py        # 演示脚本
```
