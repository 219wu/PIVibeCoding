#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit skill 同步工具
======================

项目内的 skill/vibekit 是源，~/.pi/agent/skills/vibekit 是安装副本（pi 实际加载的）。
两者漂移会导致：改了 SKILL.md 但 pi 里不生效 / 安装副本缺文件（如 scripts/）。

用法：
  python sync_skill.py --check        # 只对比，不复制；有差异退出码 1
  python sync_skill.py --yes          # 确认后从项目副本覆盖安装副本
  python sync_skill.py --from DIR --to DIR --yes   # 自定义源/目标
"""
import argparse
import difflib
import filecmp
import os
import shutil
import sys

DEFAULT_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEFAULT_DST = os.path.join(os.path.expanduser("~"), ".pi", "agent", "skills", "vibekit")

IGNORE_DIRS = {"__pycache__", ".git"}
IGNORE_FILES = {".DS_Store"}


def walk_files(root):
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if fn in IGNORE_FILES:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            result[rel] = full
    return result


def diff_file(a, b):
    try:
        with open(a, "r", encoding="utf-8") as fa:
            la = fa.readlines()
        with open(b, "r", encoding="utf-8") as fb:
            lb = fb.readlines()
    except (OSError, UnicodeDecodeError):
        return None
    return list(difflib.unified_diff(la, lb, fromfile=a, tofile=b, lineterm=""))


def cmd_check(args):
    src, dst = os.path.abspath(args.src), os.path.abspath(args.dst)
    files_src = walk_files(src)
    files_dst = walk_files(dst)

    only_src = sorted(set(files_src) - set(files_dst))
    only_dst = sorted(set(files_dst) - set(files_src))
    common = sorted(set(files_src) & set(files_dst))
    different = [f for f in common if not filecmp.cmp(files_src[f], files_dst[f], shallow=False)]

    print(f"源（项目）: {src}")
    print(f"目标（安装）: {dst}")
    print(f" 项目独有（安装缺失）: {len(only_src)}")
    for f in only_src:
        print(f"   + {f}")
    print(f" 安装独有（项目删除）: {len(only_dst)}")
    for f in only_dst:
        print(f"   - {f}")
    print(f" 内容不同: {len(different)}")
    for f in different:
        print(f"   ~ {f}")

    if only_src or only_dst or different:
        print()
        print("存在差异，运行: python sync_skill.py --yes 同步")
        return 1
    print("完全一致 ✓")
    return 0


def cmd_sync(args):
    src, dst = os.path.abspath(args.src), os.path.abspath(args.dst)
    if not os.path.isdir(src):
        print(f"[FAIL] 源目录不存在: {src}")
        return 1
    if not args.yes:
        print("将用项目副本覆盖安装副本（会覆盖安装副本中的所有文件）。")
        print("建议先运行 --check 查看差异。")
        ans = input(f"确认覆盖 {dst} ? [y/N] ").strip().lower()
        if ans != "y":
            print("已取消")
            return 1

    files_src = walk_files(src)
    for rel, full in files_src.items():
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(full, target)
        print(f"  → {rel}")

    # 清理安装副本中项目已删除的文件
    files_dst = walk_files(dst)
    for rel in files_dst:
        if rel not in files_src:
            os.remove(files_dst[rel])
            print(f"  ✗ 删除（项目已移除）: {rel}")

    print(f"同步完成: {len(files_src)} 个文件 → {dst}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="vibekit skill 同步工具")
    parser.add_argument("--src", default=DEFAULT_SRC, help="源（项目内 skill/vibekit）")
    parser.add_argument("--dst", default=DEFAULT_DST, help="目标（~/.pi/agent/skills/vibekit）")
    parser.add_argument("--check", action="store_true", help="只对比不复制")
    parser.add_argument("--yes", action="store_true", help="跳过确认直接同步")
    args = parser.parse_args()

    if args.check:
        return cmd_check(args)
    return cmd_sync(args)


if __name__ == "__main__":
    sys.exit(main())
