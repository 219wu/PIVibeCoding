# 七阶段流水线详解

Vibe Coding 的核心矛盾：**AI 写代码快，但"快"不等于"对"**。
七阶段流水线把速度转化为可控交付，每一阶段都是一道质量关卡。

## 任务分级（先分级，再选流程）

| 类型 | 判定标准 | 流程 |
|------|----------|------|
| **大任务** | 新功能 / 重构 / 跨 3+ 文件 / 涉及架构 | 完整七阶段 |
| **小任务** | 单文件 / 配置 / 文案 / 依赖升级 | ①构思→④执行→⑤验证→⑦集成 |
| **修复任务** | Bug 修复 | 复现→③隔离→④执行→⑤验证→⑥审查→⑦集成 |

## 强制 git 检查点（对抗"两步退回"，工具强制）

| 检查点 | 时机 | 动作 |
|:---:|------|------|
| A | ③ 隔离 | `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py a`：确认工作区干净/记录已有改动 |
| B | ④ 执行后 | `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py b --boundary .vibe/boundary.json`：自动核对改动 vs 边界声明，多改/漏改 FAIL（退出码非 0） |
| C | ⑤ 验证前 | `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py c`：确认存在回滚点（HEAD/stash），无则 FAIL |

> 脚本已全局安装（`~/.pi/agent/skills/vibekit/scripts/`），**任何项目目录**都能调用。
> Windows cmd 下用 `%USERPROFILE%\.pi\agent\skills\vibekit\scripts\xxx.py`。

> 检查点工具把"让模型自觉跑 git 命令"升级为"不做就过不去"——
> 这是对抗"AI 加功能 D 弄坏 A/B/C"（两步退回）的工程化防线。
> 首次使用先 `checkpoint.py boundary-init` 生成边界声明模板。

## 工具链（scripts/）

| 工具 | 用途 |
|------|------|
| `checkpoint.py` | 强制 git 检查点 A/B/C + 边界声明模板（a / b / c / boundary-init / status） |
| `prepare_review.py` | 生成审查输入包（信息隔离：只含 diff+验收标准+审查指令） |
| `adr.py` | ADR 决策记录落盘（new / list / status） |
| `vibe_state.py` | 任务状态追踪（start / phase / next / status / done） |
| `sync_skill.py` | 同步 skill 到安装副本（--check 对比 / --yes 覆盖） |

## 状态追踪（.vibe/state.json）

```bash
python ~/.pi/agent/skills/vibekit/scripts/vibe_state.py start "任务" large
python ~/.pi/agent/skills/vibekit/scripts/vibe_state.py phase conceive   # 推进阶段
python ~/.pi/agent/skills/vibekit/scripts/vibe_state.py status           # 查看状态
python ~/.pi/agent/skills/vibekit/scripts/vibe_state.py done             # 完成
```

支持多会话：`/skill:vibekit 继续上次任务` 从断点恢复。

## 流程图

```
需求
  │
  ▼
① 构思 Conceive ──── 需求复述 + 验收标准（可测）
  │
  ▼
② 计划 Plan ──────── 任务清单 + 文件规划 + 风险点
  │
  ▼
③ 隔离 Isolate ───── 改动边界声明（新增/修改/不动）
  │
  ▼
④ 执行 Execute ───── 实现代码（按计划逐任务）
  │
  ▼
⑤ 验证 Verify ────── 真实运行输出（测试/语法/运行）
  │         │
  │   发现问题 → 回到 ④
  ▼
⑥ 审查 Review ────── 对照验收标准 + 主动找 bug
  │         │
  │   大问题 → 回到 ②
  ▼
⑦ 集成 Integrate ─── 文档 + 提交 + 交付总结
```

## 各阶段细则

### ① 构思 Conceive

输入：用户一句话需求。输出：**双方确认的理解 + 可测验收标准**。

- 问清楚：做什么、给谁用、输入输出、成功的定义
- 把模糊需求变成可测清单：
  - ❌ "优化登录"（模糊）
  - ✅ "登录接口 3 秒内返回，错误密码返回 401 且提示明确"（可测）

### ② 计划 Plan

输入：确认后的需求。输出：**编号任务清单 + 文件规划 + 风险点**。

- 每个子任务一个明确产出，可独立验证
- 技术方案写清楚：文件结构、依赖、接口
- 主动标注风险点：最容易出问题的环节提前说

### ③ 隔离 Isolate

输入：计划。输出：**改动边界声明**。

- 明确"新增/修改/不动"三张清单
- 最小化改动：不顺手重构无关代码
- 回滚方案：改坏了怎么恢复（git 或备份）

### ④ 执行 Execute

输入：计划 + 边界。输出：代码。

- 按任务清单逐项实现，每项同步进度
- 遵循项目既有风格（命名/注释/结构）
- 框架调用检查点：确认 API 参数传递链完整（本项目教训见下）

### ⑤ 验证 Verify

输入：代码。输出：**真实运行证据**。

- 必做其一：跑测试 / 执行程序 / 语法检查 / mock 拦截请求
- 检查功能正确 + 边界情况 + 错误处理
- 有输出才算验证：命令 + 结果 + 结论
- 失败 → 回到 ④，修完再验证

### ⑥ 审查 Review（独立审查，非自审）

输入：验证通过的代码。输出：**审查报告（.vibe/review/review.md）**。

- **信息隔离**：`python ~/.pi/agent/skills/vibekit/scripts/prepare_review.py --acceptance "验收标准"`
  生成输入包（diff + 验收标准 + 审查指令），审查者只读这个包，不看编写者的自我解释
- **模型分离**：编写 flash → 审查 `/model deepseek-v4-pro`（自写自审 = 同源幻觉/确认偏误）
- 按 `references/review.md` 对抗性审查协议：默认假设有 bug、逐条证伪、每条发现带证据、主动找挂点
- 对照①的验收标准逐条过；S/A 级问题回 ④ 修复后重新生成审查包再审；小问题直接修

### ⑦ 集成 Integrate

输入：审查通过的代码。输出：交付。

- 更新文档（README/注释/变更记录）
- **ADR 决策记录**：`python ~/.pi/agent/skills/vibekit/scripts/adr.py new "标题"` 生成
  docs/decisions/ADR-0001-*.md，填写背景/决策/备选方案/理由/影响——对抗隐性上下文问题
- git commit 或输出变更摘要
- 总结：交付了什么、遗留什么、下次注意什么

## 本项目教训：框架参数传递检查

参考 `D:\No.1\practice\AIMianshi\docs\model-selection.md` 第 78-87 行：

```
❌ 错误：llm.bind(extra_body=...).with_structured_output(...)
✅ 正确：llm.with_structured_output(..., extra_body=...)
```

**对流水线的意义**：
1. ②计划阶段：涉及框架 API 的任务，风险点里标注"参数传递链"
2. ④执行阶段：按正确用法写，不依赖"看起来对"
3. ⑤验证阶段：用 mock 拦截实际请求 payload，断言参数真的到了请求里
   ——这是"能拦截此类 bug 的关键一步"

## 使用建议

- 大任务（新功能）→ 完整七阶段
- 小任务（改一行配置）→ 可合并执行/验证/审查，但构思和集成不省略
- 方向不明的任务 → 卡在 ① 构思，直到验收标准清晰
