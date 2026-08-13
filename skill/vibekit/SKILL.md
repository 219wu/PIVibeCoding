---
name: vibekit
description: Vibe Coding 七阶段流水线（构思→计划→隔离→执行→验证→审查→集成），按任务类型分级（大任务完整流程/小任务精简/修复任务专项），带强制 git 检查点与 .vibe/state.json 状态追踪。当用户要求以 Vibe Coding 方式开发、用 /vibe 流程、或需要结构化质量关卡的开发任务时使用。
---

# Vibekit：七阶段 Vibe Coding 流水线

Vibe Coding 不是"随便让 AI 写代码"，而是**用结构化流水线把 AI 的高速产出变成可靠交付**。
本技能把每个开发任务拆成七阶段，按任务类型分级执行，每阶段有检查点和产出物。

> **token 优化（渐进式披露）**：本文件是流程骨架，常驻上下文。
> - 进入某个阶段前 → `read ~/.pi/agent/skills/vibekit/references/stages.md`（读对应小节）
> - 规则冲突/状态恢复/完整规则 → `read .../references/rules.md`
> - 审查协议 → `read .../references/review.md`；多角色 → `read .../references/agents.md`

## 全局安装与跨项目使用

- 技能全局安装于 `~/.pi/agent/skills/vibekit/`，**任何目录**启动 pi 都能用 `/skill:vibekit`
- 命令统一前缀：`python ~/.pi/agent/skills/vibekit/scripts/<工具>`（Windows cmd 用 `%USERPROFILE%`）
- **项目隔离**：每个项目 = 一个目录 + 一个 git 仓库；`.vibe/`、`.pi/`、git 天然按目录隔离。
  **切换项目 = 切换目录**，无需清理上下文；禁止两项目共用同目录混做。

## 一、任务分级（先分级，再选流程）

接到任务后**第一步是判定任务类型**，不同类型走不同流程，避免一刀切：

| 类型 | 判定标准 | 流程 |
|------|----------|------|
| **大任务** | 新功能 / 重构 / 跨 3 个以上文件 / 涉及架构 | 完整七阶段 |
| **小任务** | 单文件修改 / 配置调整 / 文案 / 依赖升级 | ①构思 → ④执行 → ⑤验证 → ⑦集成 |
| **修复任务** | Bug 修复 | 复现 → ③隔离 → ④执行 → ⑤验证 → ⑥审查 → ⑦集成 |

分级决策记录在状态文件里（见 references/rules.md 的状态追踪）。

## 二、七阶段总览（大任务用）

```
① 构思 → ② 计划 → ③ 隔离 → ④ 执行 → ⑤ 验证 → ⑥ 审查 → ⑦ 集成
```

| 阶段 | 目标 | 核心产出 |
|------|------|----------|
| ① 构思 Conceive | 理解需求本质，明确成功标准 | 需求理解 + 验收标准 |
| ② 计划 Plan | 拆解任务，确定技术方案 | 任务清单 + 文件规划 |
| ③ 隔离 Isolate | 最小化改动面，保证可回滚 | 改动边界声明 + git 检查 |
| ④ 执行 Execute | 实现代码 | 代码改动 |
| ⑤ 验证 Verify | 证明它真的能用 | 测试运行结果 |
| ⑥ 审查 Review | 对照需求检查质量 | 审查报告（独立审查） |
| ⑦ 集成 Integrate | 收尾：文档、提交、总结 | 变更记录 + ADR + 提交 |

> 各阶段详细操作（命令、产出物、检查点细节）见 `references/stages.md`。

## 三、检查点速查（强制，不做就过不去）

| 检查点 | 时机 | 命令 |
|:---:|------|------|
| A | ③ 执行前 | `checkpoint.py a`（记录已有改动，B 阶段区分） |
| B | ④ 执行后 | `checkpoint.py b --boundary .vibe/boundary.json`（多改/漏改/动 untouched → FAIL） |
| C | ⑤ 验证前 | `checkpoint.py c`（确认回滚点，无则 FAIL） |

> 首次使用先 `checkpoint.py boundary-init` 生成边界模板。hooks 已安装时
> pre-commit 自动跑检查点 B + 敏感扫描，pre-push 自动扫待推送内容。

## 四、工具索引（scripts/）

| 工具 | 用途 |
|------|------|
| `checkpoint.py` | 检查点 A/B/C + 边界声明（a / b / c / boundary-init / status） |
| `vibe_state.py` | 任务状态机（start / phase / next / status / done，自动写 audit.log） |
| `security.py` | 危险命令/敏感路径/内容扫描 + install-hooks |
| `prepare_review.py` | 审查输入包（信息隔离 + 无全量 diff，token 优化） |
| `adr.py` | ADR 决策记录 docs/decisions/（new / list / status） |
| `dashboard.py` | 可视化状态面板（终端 + `--html` 看板） |
| `metrics.py` | 度量统计（--json 可接工具） |
| `summary.py` | 任务摘要（配合 `/compact` 与跨会话恢复） |
| `init.py` | 新项目初始化（AGENTS.md + hooks + .gitignore） |
| `sync_skill.py` | 同步安装副本（--check / --yes） |

## 五、核心工作规则（完整 11 条见 references/rules.md）

1. **严格按流程推进，不要跳步**；每阶段完成先汇报产出物再前进
2. **验证必须有真实运行证据**（命令 + 输出 + 结论），不能说"应该没问题"
3. **检查点 A/B/C 必须用工具执行**——对抗"AI 加功能 D 弄坏 A/B/C"（两步退回）
4. **模型分离**：编写 flash；审查阶段**调用 `set_review_model` 工具**切换
   deepseek-v4-pro（extension 提供；不可用时用户 `/model deepseek-v4-pro`），审查完
   调 `set_writer_model` 切回；审查只读输入包（信息隔离）
5. **安全红线**：破坏性命令先过 `check-command`；密钥文件禁止读写；hooks 不得绕过
6. **ADR 强制**：有决策必须落盘 docs/decisions/
7. **模型路由**：阶段×模型×思考层级见 `references/rules.md` 第三节（构思/审查 pro-high，
   执行 flash-high，隔离/验证/集成 flash-low），动态调整看触发条件，切换用 extension 工具

## 六、使用方式

```bash
/skill:vibekit <任务描述>          # 新任务：自动分级 → 走对应流程
/skill:vibekit 继续上次任务        # 读 .vibe/state.json 从断点恢复
```

例如：
```bash
/skill:vibekit 为项目添加一个 Redis 缓存层        # 大任务 → 完整七阶段
/skill:vibekit 把登录按钮颜色改成蓝色              # 小任务 → 精简流程
/skill:vibekit 修复登录接口返回 500 的问题          # 修复任务 → 专项流程
```
