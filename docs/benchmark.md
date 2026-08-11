# Vibe Coding 开源项目调研报告

> 调研时间：2026-08 · 调研方式：GitHub 官方仓库 README 直读 + 技术社区分析

## 一、调研对象

网络受限（GitHub API/页面直连不稳定），通过 jsDelivr CDN 直读仓库文件完成调研：

| 项目 | 类型 | 参考点 |
|------|------|--------|
| [anthropics/skills](https://github.com/anthropics/skills) | 官方 Agent Skills 技能库 | **SKILL.md 最佳写法**（渐进式披露） |
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | 官方 AI Coding Agent | Agent 工作流、git 集成 |
| [sst/opencode](https://github.com/sst/opencode) | 开源 AI Coding Agent（高星） | Agent 模式设计、多模型路由 |
| Vibe Coding 生态分析（cnblogs/vibe-hub） | 社区实践 | Vibe Coding 的三大坑：70% 问题、两步退回、隐性上下文 |

> 注：Vibe Kanban、awesome-claude-code 等仓库当前 404（2026 年可能改名/下线），
> 以下结论基于已读到的官方仓库 + Agent Skills 标准（agentskills.io）。

## 二、成熟实现的关键模式

### 1. 渐进式披露（progressive disclosure）— anthropics/skills

官方技能不是"一个大文件"，而是分层：

```
pdf/SKILL.md          # 主流程 + 快速上手（常驻上下文）
pdf/REFERENCE.md      # 详细 API 参考（按需加载）
pdf/FORMS.md          # 特定子任务指南（按需加载）
```

frontmatter 只有 name + description（+ license），正文用 Overview → Quick Start → 分主题章节组织。

**对我们的启发**：我们的 SKILL.md 把七阶段细则全部写在主文件里，模型每次加载都消耗完整上下文。应拆分为：SKILL.md（流程总览 + 触发条件）+ references/（各阶段细则、模板）。

### 2. 按任务类型分流 — sst/opencode、claude-code

成熟 Agent 不是一套流程走到底，而是 **mode/agent 分流**：
- 计划任务（plan mode）：只调研、出方案，不写代码
- 执行任务（code mode）：实现 + 验证
- 修复任务：从复现 → 根因 → 修复（跳过构思）

**对我们的启发**：七阶段强制全程（小任务也七阶段）是过度设计。应加"任务分级"：
- 大任务（新功能）→ 完整七阶段
- 小任务（改配置/单文件）→ 合并 ④⑤⑥，保留①②⑦
- 修复任务 → 从 ③ 隔离开始

### 3. 检查点与回滚 — claude-code 的 git workflow

Claude Code 把 git 集成做成了核心能力：每步可 `git diff` 查看、可 `git checkout` 回滚。
这是对"两步退回"问题（AI 加功能 D 弄坏 A/B/C）的工程化答案。

**对我们的启发**：③ 隔离阶段应升级为**强制检查点**：
- 执行前：`git status` 确认干净 + 声明改动边界
- 执行后：`git diff --stat` 核对"只动了该动的"
- 验证前：可一键回滚的 commit

### 4. 隐性上下文与决策记录

社区共识（70% 问题）：AI 不懂"为什么选 A 不选 B"的隐性决策。
成熟团队用 ADR（Architecture Decision Record）记录决策。

**对我们的启发**：① 构思阶段加"决策记录"产出——为什么这么设计；
⑦ 集成阶段回写为 `docs/decisions/`。下次任务可读，避免 AI 反向推荐被否过的方案。

### 5. 状态追踪与中断恢复

Vibe Kanban 模式：把任务拆成可视化状态（Todo/Doing/Done），支持多会话推进。

**对我们的启发**：加 `.vibe/state.json`（当前阶段/产出物/下一步），
中断后可 `/skill:vibekit 继续上次任务` 从断点恢复，而不是重头来。

## 三、优化方向清单（按优先级）

| # | 优化方向 | 依据 | 工作量 | 价值 |
|:-:|----------|------|:---:|:---:|
| 1 | **任务分级**：大/小/修复三类流程，不再一刀切七阶段 | opencode 的 mode 分流 | 小 | ⭐⭐⭐ |
| 2 | **渐进式披露**：SKILL.md 拆主文件 + references/ | anthropics/skills | 中 | ⭐⭐⭐ |
| 3 | **强制 git 检查点**：执行前后 diff 核对 + 回滚点 | claude-code | 小 | ⭐⭐⭐ |
| 4 | **决策记录**：构思阶段记录"为什么"，集成阶段落盘 | 社区 70% 问题 | 小 | ⭐⭐ |
| 5 | **状态文件**：.vibe/state.json 支持中断恢复 | Vibe Kanban | 小 | ⭐⭐ |
| 6 | **思考级别联动**：构思/审查 high，执行 low（省钱提速） | DeepSeek 特性 | 小 | ⭐⭐ |

## 四、建议

**已完成实施**（2026-08）：

| # | 优化 | 状态 |
|:-:|------|------|
| 1 | 任务分级（大/小/修复三类流程） | ✅ 已实施 |
| 3 | 强制 git 检查点（A/B/C） | ✅ 已实施 |
| 5 | 状态文件（.vibe/state.json + vibe_state.py） | ✅ 已实施 |

**暂缓**：渐进式披露（重构工作量大，单文件对当前规模够用，后续 SKILL.md 膨胀后再拆）。
**可选**：决策记录落盘（4）、思考级别联动（6）。
