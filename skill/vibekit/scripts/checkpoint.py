#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 强制 git 检查点工具
===========================

把七阶段流水线的检查点 A/B/C 从"让模型自觉跑"变成"工具强制跑"：
不做就过不去（退出码非 0 即阻断）。

检查点：
  A  执行前 —— 确认工作区状态，记录"已有改动"（preexisting），防止混入本次改动
  B  执行后 —— 核对实际改动 == 边界声明（多改/漏改/动了不该动的 → FAIL）
  C  验证前 —— 确认存在回滚点（HEAD 提交或 stash）

用法：
  python checkpoint.py boundary-init                     # 生成边界声明模板 .vibe/boundary.json
  python checkpoint.py a [--allow-no-git]                # 检查点 A
  python checkpoint.py b --boundary .vibe/boundary.json  # 检查点 B
  python checkpoint.py c                                 # 检查点 C
  python checkpoint.py status                            # 查看检查点状态

状态文件：<工作目录>/.vibe/checkpoint.json（--dir 可指定工作目录）
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

CHECKPOINT_FILE = ".vibe/checkpoint.json"
BOUNDARY_TEMPLATE = ".vibe/boundary.json"

# 运行时产物：工具的自身状态/输出，不参与"任务改动"核对（即使没配 .gitignore）
RUNTIME_PREFIXES = (".vibe/", "__pycache__/", ".git/")

BOUNDARY_SCHEMA = {
    "added": ["新增文件列表，例如：skill/vibekit/scripts/new_tool.py"],
    "modified": ["修改文件列表，例如：skill/vibekit/SKILL.md"],
    "untouched": ["本次绝不触碰的文件列表，例如：docs/benchmark.md"],
    "note": "改动边界声明：只允许动 added/modified；untouched 动了就算异常。注意：必须写文件全路径，写目录会导致检查点 B 漏改误报（git -uall 按文件列出）",
}


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_git(args, cwd):
    try:
        # -c core.quotepath=false: 路径含中文/特殊字符时不转义八进制、不加引号
        r = subprocess.run(["git", "-c", "core.quotepath=false"] + args, cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        # 注意：不能用 .strip()，会剥掉首行前导空格（git porcelain 首行是 " M file"），
        # 导致后续按固定偏移解析时首字符丢失。只做尾部清理。
        return r.returncode, r.stdout.rstrip(), r.stderr.rstrip()
    except FileNotFoundError:
        return -1, "", "git 不可用（PATH 中找不到 git）"


def is_git_repo(cwd):
    rc, out, _ = run_git(["rev-parse", "--is-inside-work-tree"], cwd)
    return rc == 0 and out.strip() == "true"


def git_status_changes(cwd, include_runtime=False):
    """返回当前工作区相对 HEAD 的变更：{path: porcelain_code}（含未跟踪文件）。

    用 -uall 让未跟踪文件逐个列出（默认 git 会把未跟踪目录折叠成 dir/，
    与边界声明里的文件路径对不上）。
    默认过滤运行时产物（.vibe/、__pycache__/、.git/）。
    """
    rc, out, _ = run_git(["status", "--porcelain", "-uall"], cwd)
    changes = {}
    if rc != 0:
        return changes
    for line in out.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        code = line[:2].strip() or "??"
        path = line[3:].strip()
        if path.startswith('"'):
            try:
                path = json.loads(path)
            except Exception:
                pass
        if not include_runtime and path.startswith(RUNTIME_PREFIXES):
            continue
        changes[path] = code
    return changes


def load_boundary(path):
    if not os.path.exists(path):
        log(f"边界声明文件不存在: {path}（先运行 boundary-init 生成）", "FAIL")
        return None
    data = load_json(path)
    for key in ("added", "modified", "untouched"):
        if key not in data or not isinstance(data[key], list):
            log(f"边界声明缺少列表字段: {key}", "FAIL")
            return None
    return data


# ---------------- 检查点 A：执行前 ----------------
def cmd_a(args):
    cwd = args.dir
    if not is_git_repo(cwd):
        msg = "当前目录不是 git 仓库。七阶段流水线强制 git 检查点，请先: git init && git add -A && git commit -m 'initial'"
        if args.allow_no_git:
            log(msg, "WARN")
            log("--allow-no-git: 跳过检查点 A", "WARN")
            return 0
        log(msg, "FAIL")
        return 2

    changes = git_status_changes(cwd)
    state_path = os.path.join(cwd, CHECKPOINT_FILE)
    state = load_json(state_path)

    if not changes:
        log("检查点 A 通过：工作区干净，无已有改动", "PASS")
        state["preexisting"] = {}
    else:
        log(f"检查点 A 通过（带已有改动）：{len(changes)} 个文件在任务开始前已有变更，已记录，B 阶段将区分：", "WARN")
        for path, code in sorted(changes.items()):
            print(f"        [{code}] {path}")
        state["preexisting"] = changes

    state["a_checked_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(state_path, state)
    log(f"状态已写入 {CHECKPOINT_FILE}", "INFO")
    return 0


# ---------------- 检查点 B：执行后，核对边界 ----------------
def cmd_b(args):
    cwd = args.dir
    if not is_git_repo(cwd):
        log("当前目录不是 git 仓库，无法执行检查点 B", "FAIL")
        return 2

    boundary = load_boundary(os.path.join(cwd, args.boundary))
    if boundary is None:
        return 1

    state = load_json(os.path.join(cwd, CHECKPOINT_FILE))
    preexisting = state.get("preexisting", {})
    current = git_status_changes(cwd)

    # 本次新增变更 = 当前变更 - 任务开始前已有变更
    new_changes = {f: c for f, c in current.items() if f not in preexisting}

    declared = [f for f in (boundary.get("added", []) + boundary.get("modified", [])) if f and not f.startswith("#")]

    errors = []
    # 1) 边界声明的 added/modified 必须真的出现在变更里（漏改 = 执行不完整）
    for f in declared:
        if f not in current:
            errors.append(f"边界声明文件未出现在任何变更中（漏改/未实现？）: {f}")
    # 2) untouched 的文件不能出现在本次新增变更里（动了不该动的）
    for f in boundary.get("untouched", []):
        if f and not f.startswith("#") and f in new_changes:
            errors.append(f"不该动的文件被本次改动: {f} [{new_changes[f]}]")
    # 3) 本次新增变更里的文件必须都在边界声明内（多改 = 异常）
    for f, code in sorted(new_changes.items()):
        if f not in declared:
            errors.append(f"改动文件超出边界声明（多改/顺手重构？）: {f} [{code}]")

    print("=" * 60)
    print("检查点 B：改动 vs 边界声明核对")
    print("=" * 60)
    print(f"边界声明: added={len(boundary.get('added', []))} modified={len(boundary.get('modified', []))} untouched={len(boundary.get('untouched', []))}")
    print(f"本次新增变更: {len(new_changes)} 个文件")
    for f, code in sorted(new_changes.items()):
        print(f"        [{code}] {f}")
    if preexisting:
        print(f"（任务开始前已有变更 {len(preexisting)} 个，已排除）")

    if errors:
        for e in errors:
            log(e, "FAIL")
        log(f"检查点 B 未通过：{len(errors)} 处异常，撤销无关改动后重跑", "FAIL")
        state["b_result"] = "FAIL"
        state["b_errors"] = errors
    else:
        log("检查点 B 通过：改动与边界声明一致", "PASS")
        state["b_result"] = "PASS"
        state["b_errors"] = []

    state["b_checked_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(os.path.join(cwd, CHECKPOINT_FILE), state)
    return 0 if not errors else 1


# ---------------- 检查点 C：验证前，确认回滚点 ----------------
def cmd_c(args):
    cwd = args.dir
    if not is_git_repo(cwd):
        log("当前目录不是 git 仓库，无法执行检查点 C", "FAIL")
        return 2

    rc_head, out, _ = run_git(["rev-parse", "HEAD"], cwd)
    rc_stash, stash_out, _ = run_git(["stash", "list"], cwd)

    print("=" * 60)
    print("检查点 C：回滚点确认")
    print("=" * 60)

    rollbacks = []
    if rc_head == 0:
        rollbacks.append(f"HEAD 提交存在: {out[:12]}（回滚: git reset --hard HEAD）")
    if rc_stash == 0 and stash_out:
        first = stash_out.splitlines()[0]
        rollbacks.append(f"stash 存在: {first}（恢复: git stash pop）")

    state_path = os.path.join(cwd, CHECKPOINT_FILE)
    state = load_json(state_path)

    if not rollbacks:
        log("没有回滚点：无 HEAD 提交且无 stash。请先 git commit 当前进度或创建 stash", "FAIL")
        state["c_result"] = "FAIL"
        save_json(state_path, state)
        return 1

    for r in rollbacks:
        print(f"        ✓ {r}")

    # 有未提交改动时提醒
    changes = git_status_changes(cwd)
    if changes:
        log(f"工作区有 {len(changes)} 个未提交改动；回滚点指向 HEAD，验证若失败可 git checkout -- <文件> 丢弃改动", "WARN")

    log("检查点 C 通过：存在回滚点", "PASS")
    state["c_result"] = "PASS"
    state["c_checked_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(state_path, state)
    return 0


# ---------------- 边界声明模板 ----------------
def cmd_boundary_init(args):
    path = os.path.join(args.dir, BOUNDARY_TEMPLATE)
    if os.path.exists(path):
        log(f"边界声明已存在: {path}（如需重置请删除后重跑）", "WARN")
        return 1
    save_json(path, BOUNDARY_SCHEMA)
    log(f"边界声明模板已生成: {path}", "PASS")
    print("填写 added/modified/untouched 三张清单后，检查点 B 将按此核对。")
    return 0


# ---------------- 状态查看 ----------------
def cmd_status(args):
    cwd = args.dir
    state = load_json(os.path.join(cwd, CHECKPOINT_FILE))
    print("检查点状态:")
    if not state:
        print("  （尚未执行任何检查点）")
    for k in ("a_checked_at", "b_checked_at", "c_checked_at", "b_result", "c_result"):
        if k in state:
            print(f"  {k}: {state[k]}")
    pre = state.get("preexisting", {})
    if pre:
        print(f"  已有改动（检查点A记录）: {len(pre)} 个")
        for f in sorted(pre):
            print(f"      [{pre[f]}] {f}")
    print()
    if is_git_repo(cwd):
        changes = git_status_changes(cwd)
        print(f"当前 git 变更: {len(changes)} 个文件")
        for f, code in sorted(changes.items()):
            print(f"  [{code}] {f}")
    else:
        print("当前目录不是 git 仓库")
    return 0


def main():
    parser = argparse.ArgumentParser(description="vibekit 强制 git 检查点工具")
    parser.add_argument("--dir", default=".", help="工作目录（默认当前目录）")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("a", help="检查点 A：执行前确认工作区")
    b = sub.add_parser("b", help="检查点 B：执行后核对边界")
    b.add_argument("--boundary", default=BOUNDARY_TEMPLATE, help="边界声明 JSON 路径")
    sub.add_parser("c", help="检查点 C：验证前确认回滚点")
    sub.add_parser("boundary-init", help="生成边界声明模板")
    sub.add_parser("status", help="查看检查点状态")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0

    handler = {
        "a": cmd_a, "b": cmd_b, "c": cmd_c,
        "boundary-init": cmd_boundary_init, "status": cmd_status,
    }[args.cmd]

    # 检查点 A 的额外参数
    if args.cmd == "a":
        if "--allow-no-git" in sys.argv:
            args.allow_no_git = True
        else:
            args.allow_no_git = False

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
