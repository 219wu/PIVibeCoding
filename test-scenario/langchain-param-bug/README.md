# 验收测试：LangChain 参数丢失场景（七阶段全流程记录）

## 场景来源

本项目（AI 简历智能分析系统）真实遇到过的问题，记录在
`D:\No.1\practice\AIMianshi\docs\model-selection.md` 第 78-87 行：

> 用 LangChain `with_structured_output` 调 DeepSeek 时，
> `llm.bind(extra_body={"thinking": {"type": "disabled"}})` 的参数**丢失**，
> 导致非思考模式没生效、请求仍带思考模式 → 与强制 tool_choice 冲突报错。

**根因**：`bind()` 返回的 RunnableBinding 的 kwargs 不会传给
`with_structured_output`（其内部重建 bind_tools 时只收显式传的 kwargs）。

## 测试目标

验证七阶段流水线能否**系统性拦截**这类"框架调用错误"：
不是靠人肉经验，而是靠流程中的验证关卡。

## 七阶段执行记录

### ① 构思 Conceive

- 需求：实现一个 DeepSeek 结构化输出调用，且必须证明
  `extra_body`（thinking disabled）真实到达 API 请求
- 验收标准：mock 拦截请求 payload，断言 `extra_body` 存在且值正确
- 成功定义：`python verify.py` 退出码 0

### ② 计划 Plan

- 文件：`main.py`（调用代码）+ `verify.py`（验证工具）
- 技术方案：langchain-openai ChatOpenAI + with_structured_output；
  mock 拦截 `client.chat.completions.with_raw_response.create` 捕获 payload
- 风险点：⚠️ 框架参数传递链（正是本次要抓的问题）

### ③ 隔离 Isolate

- 新增：main.py、verify.py
- 修改：无（不碰其他代码）
- 回滚：删除两个文件即可

### ④ 执行 Execute

先按"错误用法"实现（复现 bug）：

```python
llm.bind(extra_body={"thinking": {"type": "disabled"}}) \
   .with_structured_output(Person, method="function_calling")
```

### ⑤ 验证 Verify（🔴 抓到 bug）

mock 拦截 payload 运行：

```
[FAIL] 错误用法: extra_body in payload = False
       payload keys = ['messages', 'model', 'parallel_tool_calls',
                       'stream', 'tool_choice', 'tools']
```

**验证阶段成功拦截**：参数确实丢了。如果直接跑真实调用，
只会得到 DeepSeek 的 "Thinking mode does not support this tool_choice"
错误（表现诡异、难排查）；mock 拦截让根因（参数缺失）一目了然。

### ⑥ 审查 Review

- 根因定位：`bind()` → RunnableBinding，其 kwargs 存在 `self.kwargs`；
  调 `.with_structured_output()` 时 `__getattr__` 只合并 config、
  **不传递 self.kwargs** → extra_body 丢失
- 修复方案：改为**显式传 kwargs**（langchain-openai 0.3.21+ 支持透传）

### ④' 修复执行

```python
llm.with_structured_output(
    Person, method="function_calling",
    include_raw=True,
    extra_body={"thinking": {"type": "disabled"}},   # 显式传
)
```

### ⑤' 验证通过（🟢）

```
[PASS] 正确用法: extra_body in payload = True
        extra_body = {'thinking': {'type': 'disabled'}}
[PASS] 错误用法对照: extra_body 丢失 = True（证明 bug 可被拦截）
结论：正确用法参数完整传递；错误用法参数丢失可被拦截
```

### ⑦ 集成 Integrate

- 交付：main.py（正确用法示例）+ verify.py（可复用的验证工具）
- 经验沉淀：写入 skill/docs（`框架调用检查点：验证阶段必须拦截
  payload 证明参数传递，不能只凭代码看起来对`）

## 结论

| 维度 | 结果 |
|------|------|
| 工作流能否处理该问题 | ✅ 能。验证阶段 mock 拦截 payload 直接抓出参数丢失 |
| 相比"直接写"的优势 | 不用等真实 API 报诡异错误，根因在请求发出前暴露 |
| 可复用性 | verify.py 可移植到任何"需要证明参数传递正确"的框架调用场景 |
