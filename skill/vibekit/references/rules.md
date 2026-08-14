# 工作规则与状态追踪（按需加载）

> 由 SKILL.md 按需加载。用法：`read ~/.pi/agent/skills/vibekit/references/rules.md`
> 通常只在出现规则冲突、状态恢复、或需要完整规则时读取。

## 一、完整工作规则（11 条）

1. **严格按流程推进，不要跳步**（分级后的流程为准）
2. 每阶段完成先汇报产出物，再进入下一阶段；汇报格式：
   `【阶段N/七·名称】...产出物...`
3. 需求模糊、方向变更 → 回到 ① 构思，不允许带病前进
4. 任何阶段发现问题 → 反馈到对应阶段重新执行，形成闭环
5. **验证必须有真实运行证据**：测试通过输出、命令运行结果，不能只说"应该没问题"
6. **git 检查点 A/B/C 是强制的，且必须用工具执行**：
   `checkpoint.py a / b / c`——不做就过不去（退出码非 0 即阻断）。
   这是对抗"AI 加功能 D 弄坏 A/B/C"（两步退回）的关键防线
7. **模型分离**：编写用 `deepseek-v4-flash`（默认），审查/验证阶段切换
   `/model deepseek-v4-pro`——自写自审是同源幻觉/确认偏误的来源
8. **信息隔离**：审查者只读 prepare_review.py 生成的输入包，
   不接触编写者的自我解释；验证结论由验证阶段独立得出
9. **思考级别建议**：构思/审查用 high，执行可用 low（提速省钱），由模型自行把握
10. **ADR 强制**：⑦集成有决策必须落盘 docs/decisions/（adr.py），不许只口头说
11. **安全命令红线**：破坏性命令（强制推送/删库/递归删除/管道执行远程脚本）
    执行前必须过 `security.py check-command`；密钥文件（auth.json/.env/私钥）
    禁止读写——`check-path` 会拦截；git hooks（pre-commit/pre-push）已安装时
    自动执行检查点 B 和敏感扫描，不得绕过

## 二、状态追踪（.vibe/state.json）

每个任务在工作目录维护 `.vibe/state.json`，支持中断恢复与多会话推进；
配套 `.vibe/audit.log`（审计）、`.vibe/summary.md`（摘要，配合 `/compact`）：

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
- 用户说"继续上次任务" → 先读 `.vibe/state.json`（必要时 `summary.py` 生成摘要），从 `current_phase` 恢复
- 多任务并行 → 每个任务一个目录（`.vibe/tasks/<任务名>/state.json`）
- **可视化/度量**：`dashboard.py` 看运行状态，`metrics.py` 看统计数据
- **多角色落地**：审查者用独立会话 + 切换 pro 模型（详见 `references/agents.md`）

## 三、模型路由（模型 × 思考层级）

两个可用模型（DeepSeek，能力来自 models-store.json）：

| | deepseek-v4-flash | deepseek-v4-pro |
|---|---|---|
| 支持思考层级 | **low / high / max**（无 medium） | **只有 high / max**（无 low/medium） |
| 成本（in/out） | 0.14 / 0.28 | 0.435 / 0.87（3 倍） |
| 定位 | 快、便宜、量大 | 深、贵、慢 |

### 静态路由表（默认按此执行）

| 阶段 | 模型 | 思考 | 理由 |
|:-:|:-:|:-:|------|
| ① 构思 | **pro** | high | 验收标准定错全白干——一次性质量 |
| ② 计划 | flash | high | 拆任务/风险点足够；架构级设计临时升 pro |
| ③ 隔离 | **flash** | **low** | 纯机械（检查点 A/边界声明） |
| ④ 执行 | **flash** | high | 量大价低；high 减少验证返工 |
| ⑤ 验证 | **flash** | **low** | 跑命令零思考；结果判断 low 够 |
| ⑥ 审查 | **pro** | high | 深度推理找 bug——pro 主场（独立性 > 思考层级） |
| ⑦ 集成 | **flash** | **low** | 文档/ADR/提交 = 机械+轻写作 |

切换工具（extension 提供，模型自主调用，审计记录 model_switch/thinking_switch）：
- `set_review_model` / `set_writer_model`：flash ↔ pro
- `set_thinking_level <low|high|max>`：切思考层级（pi 自动 clamp 到模型能力）

### 动态触发条件（信号驱动，不随意）

| 触发 | 调整 |
|------|------|
| 需求一句话说清（小任务） | ① 降 flash-high（省 pro） |
| 计划跨 3+ 文件 / 架构级 | ② 升 pro-high |
| 执行遇不熟的框架 API | ④ 临时 pro-high；⑤ 用 mock 拦截验证参数传递 |
| 验证反复返工（同阶段循环 2 次+） | ④ 升档——"思考不足"信号 |
| 审查 S/A 级问题多 | ⑥ 保持 pro，必要时 max |
| 极小改动（一行配置） | 全程 flash-low，⑥ 若走审查保持 pro |

### 切换纪律（防 pi 压缩崩溃）

- **切到 pro 前必须先把思考级别升到 high**（pro 只支持 high/max）。
  低级别残留（执行阶段 flash-low）会在 pi.setModel 内部触发
  getSupportedThinkingLevels 返回 undefined → 压缩崩溃（pi 0.82.1）
- extension 已内置此防御（set_review_model 先升 high 再切 pro）；
  手动 /model 切换时也遵循同样顺序：先 /settings 升 high，再 /model
- 审查结束 set_writer_model 切回 flash 后，可按路由表恢复到 low（flash 支持 low）

### 原则（面试可讲）

1. **pro 只花在"判断质量直接决定结果"的环节**（构思验收标准、审查找 bug）；
   执行写代码量大 → flash 性价比主场
2. **思考层级跟着"是否会被下游复验"走**：会被验证/审查兜底的环节可降思考；
   无兜底环节（构思/审查）必须 high
3. **flash 无 medium**——直接 low/high 二选一，不要规划 medium
4. **审查独立性 > 审查思考层级**：不同模型+信息隔离 强于 同模型 max 自审
5. **静态映射保下限，动态触发保上限**；返工信号比主观判断准

## 四、上下文管理（token 优化）

- **渐进式披露**：SKILL.md 是骨架常驻；进入阶段读 `references/stages.md` 对应小节，
  遇规则冲突读 `references/rules.md`——不一次读完全部 references
- **审查瘦身**：prepare_review.py 只生成变更清单（无全量 diff），审查者按需查看
- **自动压缩**：pi 的 compaction 默认开启（保留最近 ~20K token，更早自动摘要）；
  长任务先 `summary.py` 生成摘要，再 `/compact` 用摘要恢复脉络
- **提示缓存友好**：不频繁改写 SKILL.md/AGENTS.md（系统提示稳定 → 缓存命中率高）

## 五、错误用法示例（本项目参考教训）

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
