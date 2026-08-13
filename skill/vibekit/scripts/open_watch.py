#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 自动打开观察窗
======================

在当前项目目录执行时：
  1. 读取 .vibe/state.json 的当前任务名（无任务则用目录名）
  2. 打开一个新终端窗口，标题 = "（任务名）观察窗"
  3. 新窗口自动运行 dashboard --watch（实时状态面板）

用法：
  python open_watch.py               # 打开观察窗
  python open_watch.py --title "自定义"   # 自定义标题
  python open_watch.py --interval 1  # 刷新间隔（秒）
  python open_watch.py --plain       # 纯文本模式（旧终端兼容）

实现要点：用临时 .cmd 文件承载 watch 命令（避免 cmd 内嵌引号转义问题），
窗口标题由 start 的第一个引号参数设置。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def get_task(cwd):
    """从 .vibe/state.json 读当前任务名，失败回退到目录名。"""
    try:
        with open(os.path.join(cwd, ".vibe", "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        task = (st.get("task") or "").strip()
        if task:
            return task
    except (OSError, ValueError):
        pass
    return os.path.basename(cwd) or "未知任务"


def build_watch_cmd(cwd, dash_path, interval, plain):
    """生成观察窗内执行的批处理内容（全 ASCII，避免 cmd GBK 解析乱码）。"""
    mode = " --plain" if plain else ""
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "set PYTHONIOENCODING=utf-8",
        f'cd /d "{cwd}"',
        f'python "{dash_path}" --watch --interval {interval}{mode}',
    ]
    return "\r\n".join(lines) + "\r\n"


def main():
    parser = argparse.ArgumentParser(description="vibekit 自动打开观察窗")
    parser.add_argument("--title", default="", help="自定义窗口标题（默认取任务名）")
    parser.add_argument("--interval", type=float, default=3.0, help="刷新间隔秒数")
    parser.add_argument("--plain", action="store_true", help="纯文本模式（旧终端兼容）")
    parser.add_argument("--dir", default=".", help="工作目录")
    args = parser.parse_args()

    cwd = os.path.abspath(args.dir)
    task = args.title.strip() or get_task(cwd)
    title = f"（{task}）观察窗"

    dash = os.path.join(os.path.expanduser("~"),
                        ".pi", "agent", "skills", "vibekit", "scripts", "dashboard.py")
    if not os.path.exists(dash):
        print(f"[FAIL] dashboard.py 不存在: {dash}")
        return 1

    # 生成临时批处理（全 ASCII 写入）
    content = build_watch_cmd(cwd, dash, args.interval, args.plain)
    fd, tmp = tempfile.mkstemp(suffix=".cmd", prefix="vibekit-watch-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content.encode("ascii", errors="replace"))
        # start 打开新窗口：标题=第一个引号参数，/d 指定工作目录
        start_cmd = f'cmd /c start "{title}" /d "{cwd}" cmd /k call "{tmp}"'
        subprocess.Popen(start_cmd, shell=True)
    except Exception as e:
        print(f"[FAIL] 打开窗口失败: {e}")
        return 1

    print(f"✅ 观察窗已打开: {title}")
    print(f"   工作目录: {cwd}")
    print(f"   刷新间隔: {args.interval}s{'（纯文本）' if args.plain else ''}")
    print("   在观察窗内按 Ctrl+C 可退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
