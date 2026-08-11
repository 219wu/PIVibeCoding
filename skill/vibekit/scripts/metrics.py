#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 度量统计（Metrics）
==========================

从审计日志、git 历史、审查报告、ADR 中统计工作流运行数据，
回答"这套流程到底有没有用、花了多少、抓了多少问题"。

数据来源：
  .vibe/audit.log        任务/阶段/检查点审计
  git log                提交与时间线
  .vibe/review/review.md 审查发现的问题（严重度）
  docs/decisions/        ADR 决策数

用法：
  python metrics.py                 # 终端统计报告
  python metrics.py --json          # 输出 JSON（可接其他工具）
  python metrics.py --dir <工作目录>
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime

PHASE_CN = {"conceive": "构思", "plan": "计划", "isolate": "隔离",
            "execute": "执行", "verify": "验证", "review": "审查", "integrate": "集成"}


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def run_git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout.strip()
    except FileNotFoundError:
        return -1, ""


def collect(cwd):
    vibe = os.path.join(cwd, ".vibe")
    m = {}

    # ---- 审计日志 ----
    audit_raw = read_file(os.path.join(vibe, "audit.log"))
    audit_lines = [l for l in audit_raw.splitlines() if l.strip()]
    m["audit_total"] = len(audit_lines)

    actions = Counter()
    cp_results = Counter()
    tasks = set()
    for line in audit_lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        ts, action, detail, result = parts[0], parts[1], parts[2], parts[3]
        actions[action] += 1
        if action.startswith("checkpoint_"):
            cp_results[action + ":" + result] += 1
        t = re.search(r"task=([^;]+)", detail)
        if t:
            tasks.add(t.group(1))
    m["actions"] = dict(actions)
    m["tasks_seen"] = len(tasks)
    m["checkpoint_results"] = dict(cp_results)

    # 首末审计时间
    if audit_lines:
        try:
            m["audit_first"] = audit_lines[0].split("|")[0].strip()
            m["audit_last"] = audit_lines[-1].split("|")[0].strip()
        except IndexError:
            pass

    # ---- git ----
    rc, n = run_git(["rev-list", "--count", "HEAD"], cwd)
    m["commits"] = n if rc == 0 else "0"
    rc, first = run_git(["log", "--reverse", "--format=%ai", "-1"], cwd)
    rc2, last = run_git(["log", "--format=%ai", "-1"], cwd)
    if rc == 0 and rc2 == 0 and first and last:
        try:
            d1 = datetime.fromisoformat(first[:19])
            d2 = datetime.fromisoformat(last[:19])
            m["git_days"] = round((d2 - d1).total_seconds() / 86400, 1)
        except ValueError:
            pass

    # ---- 审查报告 ----
    review = read_file(os.path.join(vibe, "review", "review.md"))
    severity = Counter()
    for s in ("S", "A", "B", "C"):
        # 表格行形如 | S | file | ... |
        cnt = len(re.findall(rf"^\|\s*{s}\s*\|", review, re.M))
        severity[s] = cnt
    m["review_severity"] = dict(severity)
    m["review_total"] = sum(severity.values())
    m["review_verdict"] = "通过" if ("**通过**" in review or "通过。验收标准" in review) else (
        "需修复" if "需修复" in review else "未审查")

    # ---- ADR ----
    decisions = os.path.join(cwd, "docs", "decisions")
    adrs = []
    if os.path.isdir(decisions):
        for name in os.listdir(decisions):
            if re.match(r"ADR-\d+-", name):
                adrs.append(name)
    m["adr_count"] = len(adrs)

    # ---- 状态机 ----
    try:
        with open(os.path.join(vibe, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        m["current_task"] = st.get("task")
        m["current_phase"] = st.get("current_phase")
    except (OSError, ValueError):
        m["current_task"] = None
        m["current_phase"] = None

    return m


def render_report(m):
    print("=" * 52)
    print("  Vibekit 工作流度量报告")
    print("=" * 52)

    print("\n【任务与流程】")
    print(f"  审计记录: {m['audit_total']} 条")
    print(f"  涉及任务: {m['tasks_seen']} 个")
    print(f"  当前任务: {m.get('current_task') or '（无）'}")
    actions = m.get("actions", {})
    if actions:
        cn = {"task_start": "任务开始", "task_done": "任务完成", "phase_done": "阶段完成",
              "checkpoint_a": "检查点A", "checkpoint_b": "检查点B", "checkpoint_c": "检查点C",
              "next_step": "记录下一步"}
        for k, v in sorted(actions.items(), key=lambda x: -x[1]):
            print(f"    {cn.get(k, k)}: {v}")

    print("\n【检查点通过率】")
    cpr = m.get("checkpoint_results", {})
    if cpr:
        for k, v in sorted(cpr.items()):
            print(f"    {k}: {v}")
    else:
        print("    （暂无数据）")

    print("\n【Git】")
    print(f"  提交数: {m['commits']}")
    if "git_days" in m:
        print(f"  时间跨度: {m['git_days']} 天")

    print("\n【审查质量】")
    sev = m.get("review_severity", {})
    print(f"  审查结论: {m.get('review_verdict')}")
    print(f"  发现问题: {m['review_total']} 个（S:{sev.get('S',0)} A:{sev.get('A',0)} "
          f"B:{sev.get('B',0)} C:{sev.get('C',0)}）")

    print("\n【决策资产】")
    print(f"  ADR: {m.get('adr_count')} 条")
    print("=" * 52)
    return 0


def main():
    parser = argparse.ArgumentParser(description="vibekit 度量统计")
    parser.add_argument("--dir", default=".", help="工作目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    m = collect(os.path.abspath(args.dir))
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return 0
    return render_report(m)


if __name__ == "__main__":
    sys.exit(main())
