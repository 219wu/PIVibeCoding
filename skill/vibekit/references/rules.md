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

## 三、上下文管理（token 优化）

- **渐进式披露**：SKILL.md 是骨架常驻；进入阶段读 `references/stages.md` 对应小节，
  遇规则冲突读 `references/rules.md`——不一次读完全部 references
- **审查瘦身**：prepare_review.py 只生成变更清单（无全量 diff），审查者按需查看
- **思考级别**：构思/审查 high、执行 low/medium（可在 /settings 调整）
- **自动压缩**：pi 的 compaction 默认开启（保留最近 ~20K token，更早自动摘要）；
  长任务先 `summary.py` 生成摘要，再 `/compact` 用摘要恢复脉络
- **提示缓存友好**：不频繁改写 SKILL.md/AGENTS.md（系统提示稳定 → 缓存命中率高）

## 四、错误用法示例（本项目参考教训）

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
