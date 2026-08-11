#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 决策记录工具（ADR / Architecture Decision Record）
==========================================================

把"为什么选 A 不选 B"的隐性决策落盘到 docs/decisions/，
对抗社区共识的 70% 问题：AI 不懂隐性上下文。

用法：
  python adr.py new "为项目添加 Redis 缓存层"
  python adr.py list
  python adr.py status
  python adr.py --dir . new "标题"

生成文件：docs/decisions/ADR-0001-为项目添加redis缓存层.md
"""
import argparse
import os
import re
import sys
from datetime import date

DECISIONS_DIR = "docs/decisions"

TEMPLATE = """# ADR-{num}: {title}

- 状态: Proposed（Proposed / Accepted / Superseded）
- 日期: {date}
- 相关任务: （.vibe/state.json 的任务描述）

## 背景（Context）

为什么需要做这个决策？触发条件是什么？

## 决策（Decision）

我们决定做什么。（一句话说清楚）

## 备选方案（Alternatives）

| 方案 | 优点 | 缺点 |
|------|------|------|
| A: ... | ... | ... |
| B: ... | ... | ... |

## 决策理由（Rationale）

为什么选这个方案而不是备选？权衡了什么？

## 影响（Consequences）

- 正面：
- 负面 / 代价：
- 未来可能需要重新审视的触发点：

## 被本决策推翻或关联的决策

- （如适用）ADR-0000: ...
"""


def slugify(title):
    """标题转文件名 slug：保留中文，空格转-，去特殊字符与控制字符，截断长度。"""
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "", title.strip())
    s = re.sub(r"\s+", "-", s)
    return s[:120]  # Windows 路径段上限约 255，留余量


def list_adrs(decisions_dir):
    """返回 [(num, title), ...] 按编号排序。"""
    adrs = []
    if not os.path.isdir(decisions_dir):
        return adrs
    for name in os.listdir(decisions_dir):
        m = re.match(r"ADR-(\d+)-(.*?)\.md$", name)
        if m:
            adrs.append((int(m.group(1)), m.group(2)))
    adrs.sort()
    return adrs


def cmd_new(args):
    cwd = args.dir
    decisions_dir = os.path.join(cwd, DECISIONS_DIR)
    os.makedirs(decisions_dir, exist_ok=True)

    adrs = list_adrs(decisions_dir)
    num = (adrs[-1][0] + 1) if adrs else 1
    if num > 9999:
        print("[FAIL] ADR 编号溢出（>9999）")
        return 1

    title = args.title
    fname = f"ADR-{num:04d}-{slugify(title)}.md"
    fpath = os.path.join(decisions_dir, fname)

    if os.path.exists(fpath):
        print(f"[FAIL] 文件已存在: {fpath}")
        return 1

    content = TEMPLATE.format(num=f"{num:04d}", title=title, date=date.today().isoformat())
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

    print("=" * 60)
    print(f"ADR 已创建: {fpath}")
    print("=" * 60)
    print("请填写: 背景 / 决策 / 备选方案 / 决策理由 / 影响")
    return 0


def cmd_list(args):
    adrs = list_adrs(os.path.join(args.dir, DECISIONS_DIR))
    if not adrs:
        print("docs/decisions/ 下暂无 ADR")
        return 0
    print(f"{'编号':<8} {'标题'}")
    print("-" * 60)
    for num, title in adrs:
        print(f"ADR-{num:04d}  {title}")
    return 0


def cmd_status(args):
    adrs = list_adrs(os.path.join(args.dir, DECISIONS_DIR))
    states = {}
    for num, title in adrs:
        path = os.path.join(args.dir, DECISIONS_DIR, f"ADR-{num:04d}-{title}.md")
        try:
            with open(path, "r", encoding="utf-8") as f:
                head = f.read(500)
            m = re.search(r"状态: (\w+)", head)
            st = m.group(1) if m else "?"
            states[st] = states.get(st, 0) + 1
        except OSError:
            pass
    print(f"ADR 总数: {len(adrs)}")
    for st, cnt in sorted(states.items()):
        print(f"  {st}: {cnt}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="vibekit ADR 决策记录工具")
    parser.add_argument("--dir", default=".", help="工作目录（默认当前目录）")
    sub = parser.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new", help="创建新 ADR")
    p_new.add_argument("title", help="决策标题（建议：为项目添加 X / 选择 Y 方案）")

    sub.add_parser("list", help="列出所有 ADR")
    sub.add_parser("status", help="ADR 状态统计")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0

    handler = {"new": cmd_new, "list": cmd_list, "status": cmd_status}[args.cmd]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
