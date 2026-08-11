#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 可视化仪表盘
====================

把 vibekit 工作流的运行状态渲染成可读面板：
任务阶段进度、检查点、git 状态、ADR、审查、审计摘要。

用法：
  python dashboard.py                 # 终端面板（ANSI 彩色，自动检测）
  python dashboard.py --plain         # 纯文本（无颜色）
  python dashboard.py --html out.html # 生成 HTML 看板（可分享/面试展示）
  python dashboard.py --dir <工作目录>
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

PHASES = [("conceive", "构思"), ("plan", "计划"), ("isolate", "隔离"),
          ("execute", "执行"), ("verify", "验证"), ("review", "审查"), ("integrate", "集成")]


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


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


class Colors:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.GREEN = "\033[32m" if enabled else ""
        self.RED = "\033[31m" if enabled else ""
        self.YELLOW = "\033[33m" if enabled else ""
        self.CYAN = "\033[36m" if enabled else ""
        self.BOLD = "\033[1m" if enabled else ""
        self.DIM = "\033[2m" if enabled else ""
        self.END = "\033[0m" if enabled else ""

    def ok(self, s): return f"{self.GREEN}{s}{self.END}"
    def bad(self, s): return f"{self.RED}{s}{self.END}"
    def warn(self, s): return f"{self.YELLOW}{s}{self.END}"
    def head(self, s): return f"{self.BOLD}{self.CYAN}{s}{self.END}"
    def dim(self, s): return f"{self.DIM}{s}{self.END}"
    def bold(self, s): return f"{self.BOLD}{s}{self.END}"


def collect(cwd):
    """收集所有面板数据。"""
    vibe = os.path.join(cwd, ".vibe")
    state = read_json(os.path.join(vibe, "state.json"))
    cp = read_json(os.path.join(vibe, "checkpoint.json"))
    boundary = read_json(os.path.join(vibe, "boundary.json"))

    # git
    rc, branch = run_git(["branch", "--show-current"], cwd)
    _, log1 = run_git(["log", "--oneline", "-1"], cwd)
    _, log_count = run_git(["rev-list", "--count", "HEAD"], cwd)
    _, status_raw = run_git(["status", "--porcelain", "-uall"], cwd)
    changes = [l for l in status_raw.splitlines() if l.strip()]
    _, head = run_git(["rev-parse", "--short", "HEAD"], cwd)

    # ADR
    decisions_dir = os.path.join(cwd, "docs", "decisions")
    adrs = []
    if os.path.isdir(decisions_dir):
        for name in os.listdir(decisions_dir):
            m = re.match(r"ADR-(\d+)-(.*?)\.md$", name)
            if m:
                content = read_file(os.path.join(decisions_dir, name))[:600]
                st = re.search(r"状态: (\w+)", content)
                adrs.append((int(m.group(1)), m.group(2), st.group(1) if st else "?"))

    # 审查
    review_prompt = read_file(os.path.join(vibe, "review", "prompt.md"))
    review_report = read_file(os.path.join(vibe, "review", "review.md"))
    diff_hash = ""
    m = re.search(r"diff hash: ([0-9a-f]{12})", review_prompt)
    if m:
        diff_hash = m.group(1)
    review_verdict = "未审查"
    if "**通过**" in review_report or "结论\n\n**通过**" in review_report or "通过。验收标准" in review_report:
        review_verdict = "通过"
    elif "需修复" in review_report:
        review_verdict = "需修复"

    # 审计
    audit_lines = [l for l in read_file(os.path.join(vibe, "audit.log")).splitlines() if l.strip()]
    audit_count = len(audit_lines)

    return {
        "state": state, "checkpoint": cp, "boundary": boundary,
        "branch": branch or "?", "log1": log1 or "(无提交)", "log_count": log_count or "0",
        "changes": changes, "head": head or "?", "adrs": adrs,
        "diff_hash": diff_hash, "review_verdict": review_verdict,
        "audit_count": audit_count,
    }


def render_terminal(d, c):
    lines = []
    state = d["state"]

    lines.append(c.head("=" * 50))
    lines.append(c.head("  Vibekit 任务状态面板"))
    lines.append(c.head("=" * 50))

    # 任务
    if state:
        lines.append(f"{c.bold('任务')}: {state.get('task', '?')}")
        ttype = {"large": "大任务(七阶段)", "small": "小任务(精简)", "fix": "修复任务"}.get(
            state.get("task_type", ""), state.get("task_type", "?"))
        lines.append(f"{c.bold('类型')}: {ttype}")
        cur = state.get("current_phase", "?")
        status = c.ok("✅ 已完成") if cur == "done" else c.warn(f"⏳ {cur}")
        lines.append(f"{c.bold('状态')}: {status}")
    else:
        lines.append(c.warn("（当前目录没有进行中的任务，运行 /skill:vibekit 开始）"))

    # 阶段进度
    phases = state.get("phases", {})
    marks = []
    for key, cn in PHASES:
        st = phases.get(key, "todo")
        if st == "done":
            marks.append(c.ok(f"{cn}✓"))
        elif st == "in_progress":
            marks.append(c.warn(f"{cn}▶"))
        else:
            marks.append(c.dim(cn))
    lines.append(f"{c.bold('阶段')}: {' '.join(marks)}")

    # 检查点
    cp = d["checkpoint"]
    def cp_mark(name):
        r = cp.get(name + "_result")
        if r == "PASS": return c.ok(f"{name.upper()}✓")
        if r == "FAIL": return c.bad(f"{name.upper()}✗")
        return c.dim(f"{name.upper()}·")
    cps = f"检查点: {cp_mark('a')} {cp_mark('b')} {cp_mark('c')}"
    if d["head"]:
        cps += c.dim(f"   回滚点: {d['head']}")
    lines.append(cps)

    # git
    lines.append(f"{c.bold('git')}: 分支 {d['branch']}  提交 {d['log_count']} 个  最近: {d['log1']}")
    if d["changes"]:
        n_changes = len(d["changes"])
        lines.append(f"   {c.warn(str(n_changes) + ' 个未提交改动')}:")
        for ch in d["changes"][:8]:
            lines.append(f"     {c.dim(ch)}")
        if n_changes > 8:
            lines.append(c.dim(f"     ... 共 {n_changes} 个"))
    else:
        lines.append(f"   {c.ok('工作区干净')}")

    # ADR
    if d["adrs"]:
        lines.append(f"{c.bold('ADR 决策')}: {len(d['adrs'])} 条")
        for num, title, st in d["adrs"][-3:]:
            stm = {"Accepted": c.ok, "Proposed": c.warn, "Superseded": c.dim}.get(st, c.dim)
            lines.append(f"   {stm(f'ADR-{num:04d}')} {title[:44]}")
    else:
        lines.append(f"{c.bold('ADR')}: {c.dim('无（docs/decisions/ 为空）')}")

    # 审查
    review = f"{c.bold('审查')}: "
    verdict = d["review_verdict"]
    if verdict == "通过":
        review += c.ok("✅ 通过")
    elif verdict == "需修复":
        review += c.bad("⚠ 需修复")
    else:
        review += c.dim("未审查")
    if d["diff_hash"]:
        review += c.dim(f"  (diff {d['diff_hash']})")
    lines.append(review)

    # 审计
    lines.append(f"{c.bold('审计')}: {d['audit_count']} 条动作记录 → .vibe/audit.log")

    # 下一步
    nxt = state.get("next_step") if state else ""
    lines.append(c.dim("-" * 50))
    lines.append(f"{c.bold('下一步')}: {nxt or '无进行中的任务'}")
    return "\n".join(lines)


def render_html(d):
    """生成 HTML 看板。"""
    state = d["state"]
    phases_html = ""
    for key, cn in PHASES:
        st = (state.get("phases") or {}).get(key, "todo")
        icon = {"done": "✅", "in_progress": "▶", "todo": "○"}.get(st, "○")
        color = {"done": "#27ae60", "in_progress": "#e67e22", "todo": "#95a5a6"}.get(st, "#95a5a6")
        phases_html += (f'<span style="background:{color};color:#fff;padding:4px 10px;'
                        f'border-radius:12px;margin:2px;font-size:13px;">{icon} {cn}</span>')

    changes_html = "".join(
        f'<div style="color:#95a5a6;font-family:monospace;font-size:12px;">{c}</div>'
        for c in d["changes"][:12]) or '<div style="color:#27ae60;">工作区干净</div>'

    adr_html = "".join(
        f'<div>ADR-{n:04d}: {t} <span style="color:{ "#27ae60" if s=="Accepted" else "#e67e22" }">[{s}]</span></div>'
        for n, t, s in d["adrs"]) or "<div style='color:#95a5a6'>无</div>"

    cp = d["checkpoint"]
    cp_html = "".join(
        f'<td style="padding:6px 10px;border:1px solid #34495e;">{k.upper()}: '
        f'{"✅" if cp.get(k+"_result")=="PASS" else "❌" if cp.get(k+"_result")=="FAIL" else "·"}</td>'
        for k in "abc")

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>Vibekit 任务面板</title>
<style>body{{font-family:'Segoe UI',system-ui,sans-serif;background:#1e272e;color:#ecf0f1;padding:24px;max-width:900px;margin:0 auto;}}
h1{{color:#00d2ff;font-size:22px;}} .card{{background:#2c3e50;border-radius:10px;padding:16px 20px;margin:12px 0;}}
h2{{font-size:15px;color:#00d2ff;margin:0 0 8px 0;}} .dim{{color:#95a5a6;font-size:12px;}}</style></head>
<body>
<h1>🧠 Vibekit 任务状态面板</h1>
<div class="dim">生成时间: {datetime.now().isoformat(timespec='seconds')} · 仓库: {d['branch']} @ {d['head']}</div>
<div class="card"><h2>📋 当前任务</h2>
<div style="font-size:15px;font-weight:600;">{state.get('task','（无进行中的任务）') if state else '（无进行中的任务）'}</div>
<div class="dim">类型: {state.get('task_type','-') if state else '-'} · 状态: {state.get('current_phase','-') if state else '-'}</div></div>
<div class="card"><h2>🚦 七阶段进度</h2><div>{phases_html}</div>
<div class="dim" style="margin-top:8px;">下一步: {state.get('next_step','-') if state else '-'}</div></div>
<div class="card"><h2>🔒 检查点</h2><table><tr>{cp_html}</tr></table>
<div class="dim">回滚点: {d['head']} · 审查: {d['review_verdict']}{' (diff '+d['diff_hash']+')' if d['diff_hash'] else ''}</div></div>
<div class="card"><h2>📦 Git</h2>
<div>分支 {d['branch']} · 提交 {d['log_count']} 个 · 最近: <span style="font-family:monospace">{d['log1']}</span></div>
{changes_html}</div>
<div class="card"><h2>📝 ADR 决策记录</h2>{adr_html}</div>
<div class="card"><h2>📜 审计</h2><div>{d['audit_count']} 条动作记录（.vibe/audit.log）</div></div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="vibekit 可视化仪表盘")
    parser.add_argument("--dir", default=".", help="工作目录（默认当前目录）")
    parser.add_argument("--plain", action="store_true", help="纯文本输出（无 ANSI 颜色）")
    parser.add_argument("--html", default="", help="输出 HTML 看板路径（如 out.html）")
    parser.add_argument("--watch", action="store_true",
                        help="实时刷新模式（终端窗口，Ctrl+C 退出）")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="刷新间隔秒数（默认 3）")
    args = parser.parse_args()

    cwd = os.path.abspath(args.dir)
    d = collect(cwd)

    if args.html:
        path = os.path.join(cwd, args.html)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_html(d))
        print(f"HTML 看板已生成: {path}")
        return 0

    if args.watch:
        return watch_loop(cwd, args.interval, args.plain)

    c = Colors(enabled=not args.plain)
    print(render_terminal(d, c))
    return 0


def watch_loop(cwd, interval, plain):
    """实时刷新终端窗口：ANSI 清屏重绘，Ctrl+C 退出。

    在 Windows Terminal / VSCode 终端 / 现代终端下可实时看到
    任务阶段、检查点、git 状态随运行变化。
    """
    import time

    clear = "\x1b[2J\x1b[H"  # 清屏 + 光标回原点
    c = Colors(enabled=not plain)
    try:
        while True:
            d = collect(cwd)
            frame = render_terminal(d, c)
            if plain:
                # 纯文本模式：不清屏，连续输出（可用 /less 查看）
                print("=" * 10, datetime.now().strftime("%H:%M:%S"), "=" * 10, flush=True)
                print(frame, flush=True)
            else:
                print(clear + frame, end="", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print()
        print("[vibekit] 已退出实时刷新（Ctrl+C）")
        return 0
    except Exception as e:
        print(f"[vibekit] watch 异常退出: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
