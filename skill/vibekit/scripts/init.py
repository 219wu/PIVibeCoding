#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 项目初始化
==================

在一个新项目目录启用 vibekit：
  1. 生成 AGENTS.md（pi 启动自动加载的项目约定——轻量常驻，等同 CLAUDE.md）
  2. 安装 git hooks（pre-commit/pre-push 安全检查）
  3. 初始化 .vibe/ 目录

用法：
  python init.py                # 当前目录初始化
  python init.py --dir <目录>
  python init.py --no-hooks     # 跳过 hooks 安装
  python init.py --no-agents    # 跳过 AGENTS.md 生成
"""
import argparse
import os
import subprocess
import sys

AGENTS_TEMPLATE = """# 项目约定（vibekit 工作流）

本目录使用 vibekit 七阶段流水线开发：构思 → 计划 → 隔离 → 执行 → 验证 → 审查 → 集成。
详细流程见 `~/.pi/agent/skills/vibekit/SKILL.md`（按需 read，不常驻）。

## 常用命令
- 开始任务: `/skill:vibekit <任务描述>`（大/小/修复自动分级）
- 继续任务: `/skill:vibekit 继续上次任务`（读 .vibe/state.json 恢复）
- 状态面板: `python ~/.pi/agent/skills/vibekit/scripts/dashboard.py`
- 检查点:   `python ~/.pi/agent/skills/vibekit/scripts/checkpoint.py a|b|c`
- 安全:     `python ~/.pi/agent/skills/vibekit/scripts/security.py check-command "<cmd>"`
- 度量:     `python ~/.pi/agent/skills/vibekit/scripts/metrics.py`

## 安全红线（违反会被 git hooks 拦截）
- 禁止提交: `.env`、`auth.json`、私钥、凭据文件
- 禁止: `rm -rf /`、`git push --force`、`drop table`、管道执行远程脚本
- 密钥只存 `~/.pi/agent/auth.json`（全局），项目内不存放
- 破坏性命令执行前先过 `check-command`

## 流程要求
- 检查点 A/B/C 必须用工具执行（`checkpoint.py`），不做就过不去
- 执行后 `checkpoint.py b` 核对改动与 `.vibe/boundary.json` 边界一致
- 审查阶段切换 `/model deepseek-v4-pro`，只读 `prepare_review.py` 生成的输入包
- 有设计决策写 ADR（`adr.py new "标题"` → docs/decisions/）
- 提交信息清晰描述变更；每任务一个 commit

## 上下文管理
- 长任务用 `/compact` + `summary.py` 生成的摘要恢复脉络
- 切换项目 = 切换目录（每个项目独立 .vibe/、git、会话）
"""


def run_py(script, args, cwd):
    """调用全局 vibekit 脚本。"""
    script_path = os.path.join(
        os.path.expanduser("~"), ".pi", "agent", "skills", "vibekit", "scripts", script)
    if not os.path.exists(script_path):
        # 回退到本脚本同目录
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    cmd = [sys.executable, script_path] + args
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    parser = argparse.ArgumentParser(description="vibekit 项目初始化")
    parser.add_argument("--dir", default=".", help="项目目录（默认当前目录）")
    parser.add_argument("--no-hooks", action="store_true", help="跳过 hooks 安装")
    parser.add_argument("--no-agents", action="store_true", help="跳过 AGENTS.md 生成")
    args = parser.parse_args()

    cwd = os.path.abspath(args.dir)
    os.makedirs(cwd, exist_ok=True)
    print(f"vibekit 初始化: {cwd}")
    print("=" * 52)

    # 1. AGENTS.md
    if not args.no_agents:
        agents_path = os.path.join(cwd, "AGENTS.md")
        if os.path.exists(agents_path):
            print(f"[SKIP] AGENTS.md 已存在: {agents_path}")
        else:
            with open(agents_path, "w", encoding="utf-8") as f:
                f.write(AGENTS_TEMPLATE)
            print(f"[OK] 已生成 AGENTS.md（{len(AGENTS_TEMPLATE)} 字符，pi 启动自动加载）")

    # 2. git hooks
    if not args.no_hooks:
        if os.path.isdir(os.path.join(cwd, ".git")):
            rc, out = run_py("security.py", ["install-hooks"], cwd)
            print(f"[{'OK' if rc == 0 else 'FAIL'}] hooks: {out.splitlines()[-1] if out else ''}")
        else:
            print("[WARN] 非 git 仓库，跳过 hooks（先 git init）")

    # 3. .vibe 目录
    vibe = os.path.join(cwd, ".vibe")
    os.makedirs(vibe, exist_ok=True)
    print(f"[OK] 已初始化 .vibe/（任务状态目录）")

    # 4. gitignore 检查
    gi = os.path.join(cwd, ".gitignore")
    if os.path.exists(gi):
        with open(gi, "r", encoding="utf-8") as f:
            content = f.read()
        if ".vibe/" not in content:
            with open(gi, "a", encoding="utf-8") as f:
                f.write("\n# vibekit 运行时状态\n.vibe/\n__pycache__/\n*.pyc\n")
            print("[OK] .gitignore 已追加 .vibe/ 规则")
        else:
            print("[SKIP] .gitignore 已含 .vibe/ 规则")
    else:
        with open(gi, "w", encoding="utf-8") as f:
            f.write(".vibe/\n__pycache__/\n*.pyc\n")
        print("[OK] 已创建 .gitignore（含 .vibe/ 规则）")

    print("=" * 52)
    print("完成。下一步：")
    print("  1. 进入目录启动 pi（信任项目）")
    print("  2. /skill:vibekit <你的第一个任务>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
