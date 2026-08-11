#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 审查输入包生成器（信息隔离）
====================================

六阶段"审查"的前置工具：
把「代码 diff + 验收标准 + 审查指令」机械打包成 .vibe/review/prompt.md，
审查者只读这个包——**不接触编写者的自我解释**，规避同源幻觉/确认偏误。

用法：
  python prepare_review.py --acceptance "验收标准1；验收标准2；..."
  python prepare_review.py --acceptance-file .vibe/acceptance.md
  python prepare_review.py --acceptance "..." --with-context 备注.md
                           --out .vibe/review/prompt.md --dir .

参数：
  --acceptance      验收标准文本（必填其一，来自①构思阶段）
  --acceptance-file 验收标准文件（与 --acceptance 二选一）
  --with-context    可选：编写者补充上下文文件（会标记为"单方陈述"）
  --out             输出路径（默认 .vibe/review/prompt.md）
  --dir             工作目录（默认当前目录）
"""
import argparse
import hashlib
import os
import subprocess
import sys
from datetime import datetime

REVIEW_PROTOCOL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "references", "review.md")


def run_git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return -1, "", "git 不可用"


def git_diff(cwd):
    """工作区相对 HEAD 的完整 diff（含未跟踪文件说明）。"""
    rc, out, _ = run_git(["diff", "HEAD", "--no-color"], cwd)
    diff = out if rc == 0 else ""
    # 未跟踪文件（-c core.quotepath=false：中文/特殊字符路径不转义八进制）
    rc2, untracked, _ = run_git(["-c", "core.quotepath=false",
                                 "ls-files", "--others", "--exclude-standard"], cwd)
    if rc2 == 0 and untracked.strip():
        diff += "\n# 以下为未跟踪（新增）文件，请用 read 工具查看内容：\n"
        for f in untracked.splitlines():
            diff += f"#   + {f}\n"
    return diff


def git_stat(cwd):
    rc, out, _ = run_git(["diff", "HEAD", "--stat", "--no-color"], cwd)
    return out if rc == 0 else ""


def main():
    parser = argparse.ArgumentParser(description="vibekit 审查输入包生成器")
    parser.add_argument("--acceptance", default="", help="验收标准（来自①构思）")
    parser.add_argument("--acceptance-file", default="", help="验收标准文件")
    parser.add_argument("--with-context", default="", help="编写者补充上下文文件（标记为单方陈述）")
    parser.add_argument("--out", default=".vibe/review/prompt.md", help="输出路径")
    parser.add_argument("--dir", default=".", help="工作目录")
    args = parser.parse_args()

    cwd = os.path.abspath(args.dir)

    # 验收标准
    if args.acceptance_file:
        with open(args.acceptance_file, "r", encoding="utf-8") as f:
            acceptance = f.read().strip()
    else:
        acceptance = args.acceptance.strip()
    if not acceptance:
        print("[FAIL] 必须提供验收标准：--acceptance \"...\" 或 --acceptance-file 路径")
        return 1

    # 收集 diff
    diff = git_diff(cwd)
    stat = git_stat(cwd)
    if not diff and not stat:
        print("[WARN] 没有检测到工作区改动（diff HEAD 为空）。审查包将只含验收标准。")

    diff_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()[:12]

    # 审查指令（内嵌检查清单，保证输入包自包含；完整协议见 review.md）
    protocol_checks = (
        "## 审查指令（对抗性审查，完整协议见 ~/.pi/agent/skills/vibekit/references/review.md）\n"
        "你是独立代码审查员。默认假设代码里有 bug，逐条证伪。\n"
        "1. 验收标准逐条对照：可测？满足？证据？\n"
        "2. 功能正确性：逻辑、边界（空/0/None/超长）、错误处理、退出码\n"
        "3. 框架调用参数传递链：有没有 bind(...).b(...) 这类参数可能丢失的链式调用？\n"
        "4. 安全：路径/命令注入、密钥泄露、不可信输入\n"
        "5. 兼容性：Windows 路径/编码（GBK 控制台 vs UTF-8 文件）\n"
        "6. 代码质量：命名、重复、注释与代码一致\n"
        "7. 主动找挂点：至少推演 1 个'这个实现会在什么场景挂掉'的场景\n"
        "每条发现必须带证据（文件:行 + 命令输出），禁止'应该没问题'这类无证据表述。\n"
        "输出：.vibe/review/review.md（格式见 references/review.md 第三节）"
    )

    prompt = f"""# 独立审查任务（对抗性审查输入包）

> 由 prepare_review.py 机械生成于 {datetime.now().isoformat(timespec='seconds')}
> diff hash: {diff_hash}
> **信息隔离规则**：审查者只依据本文件内容审查；编写者的口头解释不得作为证据。

## 一、验收标准（来自①构思阶段，逐条对照）

{acceptance}

## 二、变更概况（git diff HEAD --stat）

{stat or '（无）'}

## 三、代码 diff

```diff
{diff}
```

## 四、审查指令

{protocol_checks}

## 五、编写者补充上下文（单方陈述，审查者须独立验证，不可直接采信）

{ctx if (ctx := _read_context(args.with_context)) else '（无）'}
"""

    out_path = os.path.join(cwd, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    print("=" * 60)
    print("审查输入包已生成")
    print("=" * 60)
    print(f"  路径: {out_path}")
    print(f"  diff hash: {diff_hash}（审查报告应记录此 hash 保证版本一致）")
    print()
    print("下一步（审查阶段）:")
    print("  1. /model deepseek-v4-pro        # 切换审查模型（模型分离）")
    print(f"  2. 读取 {out_path}，按 references/review.md 协议审查")
    print("  3. 审查结论写入 .vibe/review/review.md")
    return 0


def _read_context(path):
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError as e:
        print(f"[WARN] 无法读取 --with-context: {e}")
        return ""


if __name__ == "__main__":
    sys.exit(main())
