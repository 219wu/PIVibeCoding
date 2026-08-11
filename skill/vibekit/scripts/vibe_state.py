#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 状态管理工具
====================

管理 .vibe/state.json：开始任务、推进阶段、查询状态、继续/完成。

用法：
    python vibe_state.py start <任务名> <large|small|fix>
    python vibe_state.py phase <阶段名>          # 标记阶段完成并推进
    python vibe_state.py next <下一步描述>        # 记录下一步
    python vibe_state.py status                   # 查看当前状态
    python vibe_state.py done                     # 标记任务完成

状态文件位置：<工作目录>/.vibe/state.json（可用 --dir 指定）
"""
import argparse
import json
import os
import sys
from datetime import datetime

PHASES = ["conceive", "plan", "isolate", "execute", "verify", "review", "integrate"]
PHASE_CN = {
    "conceive": "构思", "plan": "计划", "isolate": "隔离",
    "execute": "执行", "verify": "验证", "review": "审查", "integrate": "集成",
}


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(path: str, state: dict) -> None:
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def audit(dir_: str, action: str, detail: str, result: str = "ok") -> None:
    """追加审计日志（.vibe/audit.log），供 metrics/dashboard 统计。

    格式（管道分隔，易解析）：
      TS | action | detail | result
    """
    log_path = os.path.join(dir_, ".vibe", "audit.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"{ts} | {action} | {detail} | {result}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def audit_state(dir_: str, action: str, state: dict) -> None:
    """带当前任务上下文的审计（detail 含任务名）。"""
    task = state.get("task", "?")
    detail = f"task={task};phase={state.get('current_phase', '?')}"
    audit(dir_, action, detail)


def cmd_start(args) -> int:
    path = os.path.join(args.dir, ".vibe", "state.json")
    state = {
        "task": args.task,
        "task_type": args.task_type,
        "current_phase": "conceive" if args.task_type == "large" else "execute",
        "next_step": "开始阶段：构思（明确需求与验收标准）",
        "phases": {p: "todo" for p in PHASES},
    }
    save_state(path, state)
    audit(args.dir, "task_start", f"task={args.task};type={args.task_type}")
    print(f"[vibekit] 任务已开始: {args.task} ({args.task_type})")
    print(f"[vibekit] 当前阶段: {PHASE_CN[state['current_phase']]}"
          f" → 下一步: {state['next_step']}")
    return 0


def cmd_phase(args) -> int:
    path = os.path.join(args.dir, ".vibe", "state.json")
    state = load_state(path)
    if not state:
        print("[vibekit] 错误：没有进行中的任务，先运行 start")
        return 1
    phase = args.phase
    if phase not in PHASES:
        print(f"[vibekit] 错误：未知阶段 {phase}，可用: {PHASES}")
        return 1
    state["phases"][phase] = "done"
    # 找下一个未完成阶段
    order = ["conceive", "plan", "isolate", "execute", "verify", "review", "integrate"]
    next_phase = None
    for p in order:
        if state["phases"].get(p) != "done":
            next_phase = p
            break
    if next_phase:
        state["current_phase"] = next_phase
        print(f"[vibekit] 阶段完成: {PHASE_CN[phase]} → 当前: {PHASE_CN[next_phase]}")
    else:
        state["current_phase"] = "done"
        print(f"[vibekit] 阶段完成: {PHASE_CN[phase]} → 任务全部阶段完成，"
              "记得执行 done 归档")
    save_state(path, state)
    audit(args.dir, "phase_done", f"task={state.get('task','?')};phase={phase}")
    return 0


def cmd_next(args) -> int:
    path = os.path.join(args.dir, ".vibe", "state.json")
    state = load_state(path)
    if not state:
        print("[vibekit] 错误：没有进行中的任务")
        return 1
    state["next_step"] = args.desc
    save_state(path, state)
    audit(args.dir, "next_step", f"task={state.get('task','?')};desc={args.desc[:50]}")
    print(f"[vibekit] 下一步已记录: {args.desc}")
    return 0


def cmd_status(args) -> int:
    path = os.path.join(args.dir, ".vibe", "state.json")
    state = load_state(path)
    if not state:
        print("[vibekit] 无进行中的任务")
        return 0
    print(f"任务: {state.get('task')}")
    print(f"类型: {state.get('task_type')}")
    print(f"当前阶段: {state.get('current_phase')}")
    print(f"下一步: {state.get('next_step', '')}")
    print("阶段状态:")
    for p in PHASES:
        st = state["phases"].get(p, "todo")
        mark = {"done": "[DONE]", "in_progress": "[RUN ]", "todo": "[TODO]"}.get(st, "[TODO]")
        print(f"  {mark} {PHASE_CN[p]} ({p})")
    print(f"更新时间: {state.get('updated_at', '')}")
    return 0


def cmd_done(args) -> int:
    path = os.path.join(args.dir, ".vibe", "state.json")
    state = load_state(path)
    if not state:
        print("[vibekit] 无进行中的任务")
        return 1
    state["current_phase"] = "done"
    state["next_step"] = "任务已完成"
    save_state(path, state)
    audit(args.dir, "task_done", f"task={state.get('task','?')}")
    print(f"[vibekit] 任务已标记完成: {state.get('task')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="vibekit 状态管理工具")
    parser.add_argument("--dir", default=".", help="工作目录（默认当前目录）")
    sub = parser.add_subparsers(dest="cmd")

    p_start = sub.add_parser("start", help="开始任务")
    p_start.add_argument("task", help="任务描述")
    p_start.add_argument("task_type", choices=["large", "small", "fix"],
                         help="任务类型")

    p_phase = sub.add_parser("phase", help="标记阶段完成")
    p_phase.add_argument("phase", choices=PHASES, help="阶段名")

    p_next = sub.add_parser("next", help="记录下一步")
    p_next.add_argument("desc", help="下一步描述")

    sub.add_parser("status", help="查看状态")
    sub.add_parser("done", help="完成任务")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0

    handler = {
        "start": cmd_start, "phase": cmd_phase,
        "next": cmd_next, "status": cmd_status, "done": cmd_done,
    }[args.cmd]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
