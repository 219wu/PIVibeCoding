# 七阶段细则（按需加载：进入某阶段前先 read 本文件）

> 由 SKILL.md 按需加载。用法：`read ~/.pi/agent/skills/vibekit/references/stages.md`
> 只读当前进入阶段的对应小节，不必一次读全文。

## ① 构思 Conceive（先澄清，再定案——两轮，不一步到位）

- **第一步 读需求**：若 `.vibe/requirements.md` 存在（vibekit task 生成）先读它；
  否则用对话中的需求描述
- **第二步 列信息缺口**：识别需求中模糊/缺失/冲突的点，输出【信息缺口清单】
  （编号提问：口径、范围、约束、优先级、验收方式），写入当前回答并**停下来**
- **第三步 等用户确认**：等用户逐条回答，或回复"按你的判断来"。
  **禁止在需求模糊时直接定验收标准**——"带病前进"是返工之源
- **第四步 定稿**：吸收回答 → 输出可测验收标准 + 记录**决策理由**
  （为什么这么设计，备选方案是否考虑过）
- 产出：**需求理解 + 验收标准清单**（可测的）+ 决策记录

## ② 计划 Plan

- 拆解为可执行子任务（每任务一个明确产出）
- 确定技术方案：文件结构、依赖、接口设计
- 评估风险点：哪个环节最容易出问题（框架调用、边界情况、兼容性）
- 产出：**任务清单（编号）+ 文件规划 + 风险点**

## ③ 隔离 Isolate（含强制 git 检查点）

- **检查点 A（执行前）**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py a`，
  确认工作区干净，或把已有改动记录进 `.vibe/checkpoint.json`（B 阶段自动区分，不混入本次改动）
- 声明改动边界：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py boundary-init`
  生成 `.vibe/boundary.json`，填写新增/修改/不动三张清单
- 最小化改动原则：禁止顺手重构无关代码
- 产出：**改动边界声明（.vibe/boundary.json）+ 检查点 A 结果**

## ④ 执行 Execute

- 按计划逐任务实现，每完成一个子任务同步一次进度
- 遵循项目既有风格（命名/注释/结构）
- 框架调用检查点：确认 API 参数传递链完整（验证阶段会用真实调用/mock 拦截证明）
- **安全命令检查**：执行破坏性/危险命令前先跑
  `python ~/.pi/agent/skills/vibekit/scripts/security.py check-command "<命令>"`——
  rm -rf 根目录、git push --force、drop table 等会被拦截；
  触碰密钥文件前先 `security.py check-path <路径>`
- 产出：**代码改动**
- **检查点 B（执行后）**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py b --boundary .vibe/boundary.json`，
  工具自动核对实际改动 vs 边界声明——多改/漏改/动了不该动的会 **FAIL（退出码非 0）**，
  撤销无关改动后重跑

## ⑤ 验证 Verify

- 必做其一：运行测试 / 执行程序 / 语法检查 / mock 拦截请求 payload
- 检查项：功能正确、边界情况、错误处理
- **检查点 C（验证前）**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py c`，
  工具确认存在回滚点（HEAD 提交或 stash），无回滚点则 FAIL
- 发现问题 → 回到 ④ 修复，再验证（循环）
- 产出：**验证结果**（命令 + 输出 + 结论）

## ⑥ 审查 Review（独立审查，非自审）

- **信息隔离**：运行
  `python ~/.pi/agent/skills/vibekit/scripts/prepare_review.py --acceptance "验收标准"`
  生成 `.vibe/review/prompt.md`（变更概况 + 文件清单 + 验收标准 + 审查指令）——
  审查者只读这个包，**不看编写者的自我解释**（规避同源幻觉/确认偏误）。
  输入包不含全量 diff，审查者按需 `git diff HEAD -- <文件>` 查看（token 优化）
- **模型分离**：编写用 flash，审查切换 `/model deepseek-v4-pro`（同厂不同档位；进阶可跨厂商）
- 按 `references/review.md` 对抗性审查协议执行：默认假设有 bug 逐条证伪、
  每条发现带证据（文件:行）、主动找挂点
- 多角色落地：审查者用独立会话（/new 或 /clone），只带输入包
  （详见 `references/agents.md`）
- 对照①的验收标准逐条检查；小问题直接修；S/A 级问题回 ④ 修复后重新生成审查包再审
- 产出：**.vibe/review/review.md（审查报告）**

## ⑦ 集成 Integrate

- 更新文档（README、注释、变更记录）
- **决策记录落盘（ADR）**：有决策就运行
  `python ~/.pi/agent/skills/vibekit/scripts/adr.py new "标题"`
  生成 docs/decisions/ADR-0001-*.md，填写背景/决策/备选方案/决策理由/影响——
  对抗"AI 不懂为什么选 A 不选 B"的隐性上下文问题
- **安装安全 hooks**（新仓库首次）：
  `python ~/.pi/agent/skills/vibekit/scripts/security.py install-hooks`——
  pre-commit 自动跑检查点 B + 敏感扫描，pre-push 自动扫描待推送内容（最后防线）
- 按项目规范提交（git commit，清晰的变更摘要）
- 更新状态文件为完成
- 产出：**变更记录 + ADR（如有决策）+ 交付总结**
