---
name: vibekit
description: Vibe Coding 七阶段流水线（构思→计划→隔离→执行→验证→审查→集成），按任务类型分级（大任务完整流程/小任务精简/修复任务专项），带强制 git 检查点与 .vibe/state.json 状态追踪。当用户要求以 Vibe Coding 方式开发、用 /vibe 流程、或需要结构化质量关卡的开发任务时使用。
---

# Vibekit：七阶段 Vibe Coding 流水线

Vibe Coding 不是"随便让 AI 写代码"，而是**用结构化流水线把 AI 的高速产出变成可靠交付**。
本技能把每个开发任务拆成七阶段，按任务类型分级执行，每阶段有检查点和产出物。

## 全局安装与跨项目使用

- 本技能已**全局安装**：`~/.pi/agent/skills/vibekit/`（项目内副本用 `sync_skill.py` 同步）
- **任何工作目录**启动 pi 都能用 `/skill:vibekit`；下文命令中的
  `~/.pi/agent/skills/vibekit/scripts/xxx.py` 即全局脚本路径
  （Windows cmd 下用 `%USERPROFILE%\.pi\agent\skills\vibekit\scripts\xxx.py`）
- **项目隔离原则（重要）**：每个项目 = 一个目录 + 一个 git 仓库。
  项目的 `.vibe/`（任务状态）、`.pi/`（配置）、git 工作区天然按目录隔离；
  **切换项目 = 切换目录**，无需清理上下文。禁止两个项目共用同一目录混做
  （那会导致 `.vibe/state.json` 互相覆盖、git 改动混杂）。

## 一、任务分级（先分级，再选流程）

接到任务后**第一步是判定任务类型**，不同类型走不同流程，避免一刀切：

| 类型 | 判定标准 | 流程 |
|------|----------|------|
| **大任务** | 新功能 / 重构 / 跨 3 个以上文件 / 涉及架构 | 完整七阶段 |
| **小任务** | 单文件修改 / 配置调整 / 文案 / 依赖升级 | ①构思 → ④执行 → ⑤验证 → ⑦集成 |
| **修复任务** | Bug 修复 | 复现 → ③隔离 → ④执行 → ⑤验证 → ⑥审查 → ⑦集成 |

分级决策记录在状态文件里（见"四、状态追踪"）。

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
| ⑥ 审查 Review | 对照需求检查质量 | 审查清单 + 修复 |
| ⑦ 集成 Integrate | 收尾：文档、提交、总结 | 变更记录 + 提交 |

## 三、阶段细则

### ① 构思 Conceive

- 复述需求，确认理解正确；澄清目标/输入输出/成功标准
- 记录**决策理由**：为什么这么设计（备选方案是否考虑过）
- 产出：**需求理解 + 验收标准清单**（可测的）+ 决策记录

### ② 计划 Plan

- 拆解为可执行子任务（每任务一个明确产出）
- 确定技术方案：文件结构、依赖、接口设计
- 评估风险点：哪个环节最容易出问题（框架调用、边界情况、兼容性）
- 产出：**任务清单（编号）+ 文件规划 + 风险点**

### ③ 隔离 Isolate（含强制 git 检查点）

- **检查点 A（执行前）**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py a`，
  确认工作区干净，或把已有改动记录进 `.vibe/checkpoint.json`（B 阶段自动区分，不混入本次改动）
- 声明改动边界：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py boundary-init`
  生成 `.vibe/boundary.json`，填写新增/修改/不动三张清单
- 最小化改动原则：禁止顺手重构无关代码
- 产出：**改动边界声明（.vibe/boundary.json）+ 检查点 A 结果**

### ④ 执行 Execute

- 按计划逐任务实现，每完成一个子任务同步一次进度
- 遵循项目既有风格（命名/注释/结构）
- 框架调用检查点：确认 API 参数传递链完整（验证阶段会用真实调用/mock 拦截证明）
- 产出：**代码改动**
- **检查点 B（执行后）**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py b --boundary .vibe/boundary.json`，
  工具自动核对实际改动 vs 边界声明——多改/漏改/动了不该动的会 **FAIL（退出码非 0）**，
  撤销无关改动后重跑

### ⑤ 验证 Verify

- 必做其一：运行测试 / 执行程序 / 语法检查 / mock 拦截请求 payload
- 检查项：功能正确、边界情况、错误处理
- **检查点 C（验证前）**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py c`，
  工具确认存在回滚点（HEAD 提交或 stash），无回滚点则 FAIL
- 发现问题 → 回到 ④ 修复，再验证（循环）
- 产出：**验证结果**（命令 + 输出 + 结论）

### ⑥ 审查 Review（独立审查，非自审）

- **信息隔离**：运行 `python ~/.pi/agent/skills/vibekit/scripts/prepare_review.py --acceptance "验收标准"`
  生成 `.vibe/review/prompt.md`（diff + 验收标准 + 审查指令）——
  审查者只读这个包，**不看编写者的自我解释**（规避同源幻觉/确认偏误）
- **模型分离**：编写用 flash，审查切换 `/model deepseek-v4-pro`（同厂不同档位；进阶可跨厂商）
- 按 `references/review.md` 对抗性审查协议执行：默认假设有 bug 逐条证伪、
  每条发现带证据（文件:行）、主动找挂点
- 对照①的验收标准逐条检查；小问题直接修；S/A 级问题回 ④ 修复后重新生成审查包再审
- 产出：**.vibe/review/review.md（审查报告）**

### ⑦ 集成 Integrate

- 更新文档（README、注释、变更记录）
- **决策记录落盘（ADR）**：有决策就运行 `python ~/.pi/agent/skills/vibekit/scripts/adr.py new "标题"`
  生成 docs/decisions/ADR-0001-*.md，填写背景/决策/备选方案/决策理由/影响——
  对抗"AI 不懂为什么选 A 不选 B"的隐性上下文问题
- 按项目规范提交（git commit，清晰的变更摘要）
- 更新状态文件为完成
- 产出：**变更记录 + ADR（如有决策）+ 交付总结**

## 四、状态追踪（.vibe/state.json）

每个任务在工作目录维护 `.vibe/state.json`，支持中断恢复与多会话推进：

```json
{
  "task": "任务描述",
  "task_type": "large | small | fix",
  "current_phase": "当前阶段名",
  "next_step": "下一步要做什么",
  "phases": {
    "conceive": "done",
    "plan": "done",
    "isolate": "in_progress"
  },
  "updated_at": "2026-08-08T00:00:00"
}
```

规则：
- 每个阶段开始/完成时更新 `current_phase`、`phases`、`next_step`、`updated_at`
- 任务完成 → `current_phase: "done"`
- 用户说"继续上次任务" → 先读 `.vibe/state.json`，从 `current_phase` 恢复
- 多任务并行 → 每个任务一个目录（`.vibe/tasks/<任务名>/state.json`）

## 五、工作规则

1. **严格按流程推进，不要跳步**（分级后的流程为准）
2. 每阶段完成先汇报产出物，再进入下一阶段；汇报格式：
   `【阶段N/七·名称】...产出物...`
3. 需求模糊、方向变更 → 回到 ① 构思，不允许带病前进
4. 任何阶段发现问题 → 反馈到对应阶段重新执行，形成闭环
5. **验证必须有真实运行证据**：测试通过输出、命令运行结果，不能只说"应该没问题"
6. **git 检查点 A/B/C 是强制的，且必须用工具执行**：
   `checkpoint.py a / b / c`（见③④⑤）——不做就过不去（退出码非 0 即阻断）。
   这是对抗"AI 加功能 D 弄坏 A/B/C"（两步退回）的关键防线
7. **模型分离**：编写用 `deepseek-v4-flash`（默认），审查/验证阶段切换
   `/model deepseek-v4-pro`——自写自审是同源幻觉/确认偏误的来源
8. **信息隔离**：审查者只读 prepare_review.py 生成的输入包，
   不接触编写者的自我解释；验证结论由验证阶段独立得出
9. **思考级别建议**：构思/审查用 high，执行可用 low（提速省钱），由模型自行把握
10. **ADR 强制**：⑦集成有决策必须落盘 docs/decisions/（adr.py），不许只口头说

## 六、错误用法示例（本项目参考教训）

参考 `D:\No.1\practice\AIMianshi\docs\model-selection.md` 中记录的 LangChain 参数丢失问题：

```
❌ 错误：llm.bind(extra_body=...).with_structured_output(...)
   —— bind 的参数在 with_structured_output 重建请求时丢失（参数隔离）

✅ 正确：llm.with_structured_output(..., extra_body=...)
   —— 模型参数显式传给 with_structured_output（0.3.21+ 支持透传）
```

**教训**：框架调用的"正确用法"是执行阶段的检查项——遇到框架 API，
先确认参数传递链是否完整；验证阶段必须用真实调用/mock 拦截 payload
证明参数真的传到了请求里，不能只凭"代码看起来对"。

## 七、使用方式

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
