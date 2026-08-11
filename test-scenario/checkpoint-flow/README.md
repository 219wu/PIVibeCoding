# 验收测试：checkpoint.py 强制检查点（A/B/C 全流程回归）

## 场景

验证七阶段流水线的**检查点工具化**（P0 项）——把"让模型自觉跑 git 命令"
升级为"不做就过不去"：检查点 A/B/C 的语义、FAIL 路径、退出码。

## 覆盖用例

| # | 用例 | 预期 |
|:-:|------|------|
| 1 | 非 git 目录跑 A | FAIL(2)，提示 git init |
| 2 | A 干净工作区 | PASS(0) |
| 3 | B 改动 == 边界声明 | PASS(0) |
| 4 | 动了 untouched 文件 | FAIL(1)，报"不该动的文件" |
| 5 | 加了未声明文件（多改） | FAIL(1)，报"超出边界声明" |
| 6 | 漏改（声明文件未实现） | FAIL(1)，报"漏改" |
| 7 | 修复后重跑 B | PASS(0) |
| 8 | C 有 HEAD 回滚点 | PASS(0) |
| 9 | C 无 HEAD 无 stash | FAIL(1)，报"没有回滚点" |

## 运行

```bash
cd D:\No.1\practice\PIVibeCoding
python test-scenario/checkpoint-flow/test_checkpoint.py
# 预期输出：10 通过, 0 失败，退出码 0
```

## 执行记录（2026-08-11）

首轮执行发现 2 个真实 bug 并修复（这正是检查点 B 存在的意义）：

1. **首字符丢失**：`run_git` 用 `.strip()` 剥掉了 git porcelain 首行的前导空格
   （`" M README.md"` → `"M README.md"`），偏移一位导致路径首字符丢失
   （`README.md` → `EADME.md`）。修复：改用 `.rstrip()`。
2. **未跟踪目录折叠 + 中文路径转义**：git 默认把未跟踪目录折叠成 `dir/`、
   中文路径转义成八进制（`core.quotepath`）。修复：`-uall` + `-c core.quotepath=false`。

修复后 10/10 通过。结论：检查点 B 能系统性拦截"多改/漏改/动了不该动的"，
是"AI 加功能 D 弄坏 A/B/C"（两步退回）的工程化防线。
