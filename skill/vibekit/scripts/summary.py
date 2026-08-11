#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 任务摘要生成器（上下文压缩集成）
========================================

生成 .vibe/summary.md：任务脉络摘要，用于：
  1. pi /compact 时作为补充上下文（长任务 token 紧张时）
  2. 跨会话恢复（/skill:vibekit 继续上次任务 时先读摘要）
  3. 汇报材料

用法：
  python summary.py                # 生成/刷新 .vibe/summary.md
  python summary.py --stdout       # 直接打印摘要（不写文件）
  python summary.py --dir <工作目录>
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

PHASE_CN = {"conceive": "构思", "plan": "计划", "isolate": "隔离",
            "execute": "执行", "verify": "验证", "review": "审查", "integrate": "集成"}


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def run_git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout.strip()
    except FileNotFoundError:
        return -1, ""


def build(cwd):
    vibe = os.path.join(cwd, ".vibe")
    st = read_json(os.path.join(vibe, "state.json"))
    cp = read_json(os.path.join(vibe, "checkpoint.json"))
    review = read_file(os.path.join(vibe, "review", "review.md"))
    audit = [l for l in read_file(os.path.join(vibe, "audit.log")).splitlines() if l.strip()]
    _, log1 = run_git(["log", "--oneline", "-3"], cwd)
    _, branch = run_git(["branch", "--show-current"], cwd)

    lines = []
    lines.append("# 任务摘要（vibekit summary）")
    lines.append(f"\n> 生成时间: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"> 用途: /compact 补充上下文 / 跨会话恢复 / 汇报")

    if st:
        lines.append(f"\n## 当前任务")
        lines.append(f"- 任务: {st.get('task', '?')}")
        lines.append(f"- 类型: {st.get('task_type', '?')}")
        lines.append(f"- 状态: {st.get('current_phase', '?')}")
        lines.append(f"- 下一步: {st.get('next_step', '?')}")
        lines.append(f"\n## 阶段进度")
        for k, cn in PHASE_CN.items():
            mark = {"done": "✅", "in_progress": "▶", "todo": "○"}.get(
                (st.get("phases") or {}).get(k, "todo"), "○")
            lines.append(f"- {mark} {cn} ({k})")
    else:
        lines.append(f"\n（无进行中的任务）")

    lines.append(f"\n## 检查点")
    for k in "abc":
        r = cp.get(k + "_result")
        lines.append(f"- 检查点 {k.upper()}: {'✅ PASS' if r=='PASS' else '❌ FAIL' if r=='FAIL' else '○ 未执行'}")
    if cp.get("preexisting"):
        lines.append(f"- 任务开始前已有改动: {len(cp['preexisting'])} 个文件")

    lines.append(f"\n## 审查")
    verdict = "通过" if ("**通过**" in review or "通过。验收标准" in review) else (
        "需修复" if "需修复" in review else "未审查")
    n_find = len(re.findall(r"^\|\s*[SABC]\s*\|", review, re.M))
    lines.append(f"- 结论: {verdict}  发现问题: {n_find} 个")

    lines.append(f"\n## 审计")
    lines.append(f"- 审计记录: {len(audit)} 条")
    if audit:
        lines.append(f"- 最近动作: `{audit[-1]}`")

    lines.append(f"\n## Git")
    lines.append(f"- 分支: {branch or '?'}")
    lines.append(f"- 最近提交:")
    for l in (log1.splitlines() if log1 else []):
        lines.append(f"  - {l}")

    lines.append(f"\n## 决策资产")
    decisions = os.path.join(cwd, "docs", "decisions")
    adrs = [n for n in os.listdir(decisions) if re.match(r"ADR-\d+-", n)] if os.path.isdir(decisions) else []
    lines.append(f"- ADR: {len(adrs)} 条")
    for n in adrs[-3:]:
        lines.append(f"  - {n}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="vibekit 任务摘要生成器")
    parser.add_argument("--dir", default=".", help="工作目录")
    parser.add_argument("--stdout", action="store_true", help="只打印不写文件")
    args = parser.parse_args()

    cwd = os.path.abspath(args.dir)
    text = build(cwd)

    if args.stdout:
        print(text)
        return 0

    out = os.path.join(cwd, ".vibe", "summary.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"摘要已生成: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
