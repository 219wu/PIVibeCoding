# Pi Vibe Coding 工作流

基于 Pi 框架（pi-coding-agent）搭建的 Vibe Coding 开发工作流，
核心是 `/skill:vibekit` 七阶段流水线：**构思 → 计划 → 隔离 → 执行 → 验证 → 审查 → 集成**。

## 快速开始

```bash
# 1. 进入本项目目录启动 Pi（自动使用项目级 DeepSeek 配置）
cd D:\No.1\practice\PIVibeCoding
pi

# 2. 触发七阶段流水线（描述你的任务）
/skill:vibekit 为项目添加一个 Redis 缓存层
```

## 目录结构

```
PIVibeCoding/
├── README.md                 # 本文件：工作流总览
├── skill/
│   └── vibekit/
│       ├── SKILL.md              # 七阶段流水线技能（已安装到 ~/.pi/agent/skills/vibekit/）
│       ├── references/
│       │   └── review.md             # 对抗性审查协议（独立审查角色定义）
│       └── scripts/
│           ├── vibe_state.py     # 状态管理工具（.vibe/state.json）
│           ├── checkpoint.py     # 强制 git 检查点 A/B/C（不做就过不去）
│           ├── prepare_review.py # 审查输入包生成器（信息隔离）
│           ├── adr.py            # ADR 决策记录落盘
│           └── sync_skill.py     # 同步 skill 到安装副本（防版本漂移）
├── .pi/
│   └── settings.json         # 项目级 Pi 配置（锁定 DeepSeek 唯一模型）
├── docs/
│   ├── workflow.md           # 七阶段流水线详解
│   ├── deepseek-config.md    # DeepSeek 模型配置说明
│   ├── benchmark.md          # Vibe Coding 开源方案调研报告
│   └── decisions/            # ADR 决策记录（adr.py 生成）
└── test-scenario/
    └── langchain-param-bug/  # 验收测试：模拟 LangChain 参数丢失场景
        ├── README.md         # 场景说明 + 七阶段执行记录
        ├── main.py           # 复现"错误用法"的代码
        └── verify.py         # 拦截 payload 的验证脚本
```

## 模型配置（唯一 DeepSeek）

| 项 | 值 |
|----|----|
| Provider | `deepseek`（api.deepseek.com，OpenAI 兼容） |
| 主模型 | `deepseek-v4-flash`（默认，性价比高） |
| 备选 | `deepseek-v4-pro`（复杂任务可切换） |
| API Key | 全局 `~/.pi/agent/auth.json`（**用户主目录**，非项目目录）中 `deepseek` 条目；项目内 `.pi/` 仅含模型配置，**不含也不应存放密钥** |
| 思考级别 | `defaultThinkingLevel: high`（可调 minimal/low/medium/high/max） |

> 全工作流只使用 DeepSeek 模型，**编写用 flash、审查/验证切换 pro**（模型分离，规避自写自审的同源幻觉）。
> 不要切换其他厂商模型（如 GLM/OpenAI）。

## 核心工作流：/skill:vibekit 七阶段

| # | 阶段 | 目标 | 检查点 |
|:-:|------|------|--------|
| 1 | 构思 Conceive | 理解需求，定验收标准 | 需求复述 + 可测的验收清单 |
| 2 | 计划 Plan | 拆任务、定方案、标风险 | 任务清单 + 文件规划 |
| 3 | 隔离 Isolate | 最小改动、可回滚 | 边界声明 + **检查点 A**（`checkpoint.py a`） |
| 4 | 执行 Execute | 实现 | 代码 + **检查点 B**（`checkpoint.py b`，多改/漏改自动 FAIL） |
| 5 | 验证 Verify | 证明能跑 | 真实运行输出 + **检查点 C**（`checkpoint.py c`，回滚点确认） |
| 6 | 审查 Review | 独立审查（信息隔离+模型分离） | `prepare_review.py` 输入包 + pro 模型 + 审查报告 |
| 7 | 集成 Integrate | 文档 + ADR + 提交 + 总结 | 变更记录 + `adr.py` 决策落盘 + 提交 |

**任务分级**：大任务完整七阶段；小任务（单文件/配置）精简为 构思→执行→验证→集成；
修复任务从复现 + 隔离开始。

**状态追踪**：`.vibe/state.json`（`vibe_state.py` 管理），支持中断恢复、多会话推进。

**P0 工程化工具链**（详见 [docs/workflow.md](docs/workflow.md)）：

| 工具 | 作用 |
|------|------|
| `checkpoint.py` | 强制 git 检查点 A/B/C：确认工作区 → 核对改动边界 → 确认回滚点，不做就过不去（退出码非 0 阻断） |
| `prepare_review.py` | 审查输入包生成器：只打包 diff + 验收标准 + 审查指令，**排除编写者的自我解释**（信息隔离） |
| `adr.py` | ADR 决策记录落盘 docs/decisions/：把"为什么选 A 不选 B"变成可回溯的资产 |
| `sync_skill.py` | 项目 skill → 安装副本同步（--check 对比，防版本漂移） |

详见 [docs/workflow.md](docs/workflow.md)。

## 验收测试

`test-scenario/langchain-param-bug/` 模拟了项目真实遇到过的坑
（LangChain 框架用法错误导致非思考模式参数传输丢失，原记录见
`D:\No.1\practice\AIMianshi\docs\model-selection.md`），
用七阶段流水线完整走了一遍，验证阶段成功拦截了参数丢失 bug 并修复。

运行方式：

```bash
cd D:\No.1\practice\PIVibeCoding\test-scenario\langchain-param-bug
python verify.py        # 验证修复后参数正确传递（拦截 payload 断言）
python main.py          # 运行示例（需 langchain-openai + pydantic）
```

测试结论：七阶段流水线的 **验证/审查阶段能系统性拦截此类框架调用错误**，
比"写完直接跑"的 Vibe Coding 多了一道参数传递正确性的质量关卡。
