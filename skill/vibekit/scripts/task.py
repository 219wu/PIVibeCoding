#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 需求文件启动任务
========================

解决"长 prompt 在终端多行粘贴"痛点：把需求写进文件（编辑器随便写），
用本命令启动任务，模型在构思阶段从 .vibe/requirements.md 读完整需求。

用法：
  python task.py requirements.md                 # 启动大任务（默认）
  python task.py requirements.md --type fix      # 指定任务类型
  python task.py --dir <项目目录> requirements.md

流程：
  1. 读取需求文件
  2. vibe_state start 启动任务（任务名 = 文件名）
  3. 复制需求到 .vibe/requirements.md，并在 state.json 记录
  4. 提示：回 pi 输入 /skill:vibekit 继续上次任务，模型将读需求文件进入构思
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

VIBEKIT_SCRIPTS = os.path.join(os.path.expanduser("~"),
                               ".pi", "agent", "skills", "vibekit", "scripts")


def run_vibe_state(args, cwd):
    """调用全局 vibe_state.py。"""
    script = os.path.join(VIBEKIT_SCRIPTS, "vibe_state.py")
    if not os.path.exists(script):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vibe_state.py")
    cmd = [sys.executable, script, "--dir", cwd] + args
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    parser = argparse.ArgumentParser(description="vibekit 需求文件启动任务")
    parser.add_argument("file", help="需求文件路径（如 requirements.md）")
    parser.add_argument("--type", default="large", choices=["large", "small", "fix"],
                        help="任务类型（默认 large）")
    parser.add_argument("--dir", default=".", help="工作目录（默认当前目录）")
    parser.add_argument("--no-watch", action="store_true",
                        help="不自动打开观察窗")
    args = parser.parse_args()

    cwd = os.path.abspath(args.dir)
    req_path = os.path.abspath(args.file)
    if not os.path.exists(req_path):
        print(f"[FAIL] 需求文件不存在: {req_path}")
        return 1
    if not os.path.isdir(os.path.join(cwd, ".git")) and not os.path.isdir(os.path.join(cwd, ".vibe")):
        # 非 git 项目提示（vibekit 检查点需要 git）
        print(f"[WARN] {cwd} 不是 git 仓库——七阶段检查点需要 git，建议先 git init")

    # 1. 任务名 = 文件名（去扩展名）
    task_name = os.path.splitext(os.path.basename(req_path))[0]

    # 2. 启动任务（若已有进行中任务则失败，提示先 done/重置）
    rc, out = run_vibe_state(["start", task_name, args.type], cwd)
    if rc != 0:
        print(out)
        print(f"[FAIL] 启动任务失败（可能已有进行中任务，先完成或重置）")
        return 1

    # 3. 复制需求到 .vibe/requirements.md + 记录到 state.json
    vibe_dir = os.path.join(cwd, ".vibe")
    os.makedirs(vibe_dir, exist_ok=True)
    req_dst = os.path.join(vibe_dir, "requirements.md")
    shutil.copy2(req_path, req_dst)

    state_path = os.path.join(vibe_dir, "state.json")
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    state["requirements"] = ".vibe/requirements.md"
    state["requirements_source"] = req_path
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # 4. 自动打开观察窗（默认；--no-watch 关闭）
    if not args.no_watch:
        open_watch = os.path.join(VIBEKIT_SCRIPTS, "open_watch.py")
        if not os.path.exists(open_watch):
            open_watch = os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_watch.py")
        try:
            subprocess.Popen([sys.executable, open_watch, "--dir", cwd],
                             cwd=cwd, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            print("  观察窗: 已自动打开（标题=任务名）")
        except Exception as e:
            print(f"  [WARN] 观察窗自动打开失败: {e}（可手动 vibekit open-watch）")

    # 5. 提示
    print("=" * 60)
    print("✅ 任务已从需求文件启动")
    print("=" * 60)
    print(f"  任务: {task_name} ({args.type})")
    print(f"  需求来源: {req_path}")
    print(f"  已复制到: {req_dst}")
    print()
    print("下一步（pi 里）：")
    print("  /skill:vibekit 继续上次任务")
    print("  → 模型会先读 .vibe/requirements.md 进入构思阶段，")
    print("    列出信息缺口后等你确认，再定验收标准")
    return 0


if __name__ == "__main__":
    sys.exit(main())
