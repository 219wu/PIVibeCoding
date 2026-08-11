#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vibekit 安全模块：权限/安全确认 + git hooks 自动化
====================================================

两个高优先级能力：

1. 权限/安全确认（对抗"AI 乱执行命令/误碰密钥"）：
   - check-command: 危险命令拦截（rm -rf /、git push --force、drop table 等）
   - check-path:    敏感路径拦截（auth.json、.env、私钥文件等）
   - scan:          敏感内容扫描（sk-xxx、api_key=、私钥块等，最后防线）

2. hooks 自动化（把检查点从"靠模型自觉"变成"git 强制"）：
   - install-hooks: 安装 pre-commit（检查点 B + 敏感扫描）和 pre-push（推送内容扫描）
   - remove-hooks:  卸载

用法：
  python security.py check-command "git push --force origin main"
  python security.py check-path  C:/Users/x/.pi/agent/auth.json
  python security.py scan --staged            # 扫描暂存区
  python security.py scan --range origin/main..HEAD
  python security.py scan --path .env
  python security.py install-hooks [--remove]
  python security.py status
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys

# ---------------- 危险命令规则 ----------------
# (正则, 级别, 理由, 建议)  级别: BLOCK=绝对禁止 CONFIRM=需确认
DANGER_COMMANDS = [
    (re.compile(r"git\s+(push|fetch|pull)[^\n]*\s(--force|-f)\b", re.I),
     "BLOCK", "强制推送/拉取会覆盖远端历史", "如需覆盖，先确认远端无人用，且改用 --force-with-lease"),
    (re.compile(r"git\s+reset\s+--hard", re.I),
     "CONFIRM", "丢弃所有未提交改动", "先确认改动已 commit 或 stash"),
    (re.compile(r"git\s+clean\s+-(f|d|fd|df|fx|xf)\b", re.I),
     "CONFIRM", "删除未跟踪文件", "先确认这些文件不需要"),
    (re.compile(r"rm\s+(-[rfd]+)?\s+/\s|rm\s+-rf\s+~|rm\s+-rf\s+[a-z]:\\?$", re.I),
     "BLOCK", "删除根目录/家目录/盘符根", "绝对禁止：这是不可逆操作"),
    (re.compile(r"\bdel\s+/[sq]|rd\s+/s\b|format\s+[a-z]:", re.I),
     "BLOCK", "Windows 递归删除/格式化", "绝对禁止"),
    (re.compile(r"\bdrop\s+(database|table|schema)\b", re.I),
     "BLOCK", "删除数据库对象", "确认有备份且确属目标环境"),
    (re.compile(r"\b(shutdown|reboot|halt)\b", re.I),
     "CONFIRM", "关机/重启", "确认当前环境允许"),
    (re.compile(r"curl\s+[^\n|]*\|\s*(ba|z)?sh\b", re.I),
     "BLOCK", "管道直接执行远程脚本", "先下载到本地审查再执行"),
    (re.compile(r"chmod\s+-R\s+777\b", re.I),
     "CONFIRM", "递归放开所有权限", "按最小权限原则设置"),
    (re.compile(r"git\s+push[^\n]*--delete|git\s+push[^\n]*:refs/heads/", re.I),
     "CONFIRM", "删除远端分支", "确认分支已合并或确实废弃"),
    (re.compile(r">\s*~?\.pi/agent/auth\.json|>>\s*~?\.pi/agent/auth\.json", re.I),
     "BLOCK", "覆盖/追加写入全局密钥文件", "禁止"),
]

# ---------------- 敏感路径规则 ----------------
SENSITIVE_PATH_PATTERNS = [
    re.compile(r"(?i)(^|[/\\])(auth\.json|\.env(\.|$)|id_rsa|id_ed25519|id_ecdsa|id_dsa|\.netrc|credentials|secrets?([/\\]|$))"),
    re.compile(r"(?i)\.(pem|key|p12|pfx|p8|ppk)$"),
]

# ---------------- 敏感内容模式（扫描） ----------------
SENSITIVE_PATTERNS = [
    ("DeepSeek/OpenAI 密钥", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("api_key 赋值", re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*[\"']?[A-Za-z0-9+/]{24,}")),
    ("Bearer token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}")),
    ("AWS 访问密钥", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("私钥块", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----")),
    ("长口令/令牌赋值", re.compile(r"(?i)(password|passwd|secret|token)\s*[=:]\s*[\"']?[^\s\"']{12,}")),
]

WHITELIST_PREFIXES = ("sk-test",)  # 测试假密钥


def log(msg, level="INFO"):
    print(f"[{level}] {msg}")


def run_git(args, cwd="."):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false"] + args, cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return -1, "", "git 不可用"


# ================= 1. 危险命令检测 =================
def cmd_check_command(args):
    cmd = args.command
    print(f"命令: {cmd}\n")
    blocked, confirms = [], []
    for pat, level, reason, advice in DANGER_COMMANDS:
        if pat.search(cmd):
            (blocked if level == "BLOCK" else confirms).append((reason, advice, pat.pattern))

    if blocked:
        for reason, advice, _ in blocked:
            log(f"危险命令（禁止）: {reason} -> 建议: {advice}", "FAIL")
        log(f"命令被拦截，退出码 2", "FAIL")
        return 2
    if confirms:
        for reason, advice, _ in confirms:
            log(f"高危命令（需确认）: {reason} -> 建议: {advice}", "WARN")
        log("命令含高危操作，请确认意图后再执行", "WARN")
        return 0
    log("未检测到危险模式", "PASS")
    return 0


# ================= 2. 敏感路径检测 =================
def cmd_check_path(args):
    p = os.path.abspath(args.path)
    hits = [pat for pat in SENSITIVE_PATH_PATTERNS if pat.search(p)]
    if hits:
        log(f"敏感路径被拦截: {p}", "FAIL")
        log("原因: 该路径匹配密钥/凭据/私钥文件规则", "FAIL")
        return 2
    log(f"路径安全: {p}", "PASS")
    return 0


# ================= 3. 敏感内容扫描 =================
def scan_text(text, source):
    """扫描文本，返回 [(模式名, 片段)]。"""
    hits = []
    for name, pat in SENSITIVE_PATTERNS:
        for m in pat.finditer(text):
            seg = m.group(0)
            if any(seg.startswith(w) for w in WHITELIST_PREFIXES):
                continue
            hits.append((name, seg[:40]))
            break  # 每个模式每文件报一次
    return hits


def git_diff_text(spec_args):
    """按 git 参数拿 diff 文本 + 文件列表。"""
    rc, out, _ = run_git(["diff"] + spec_args)
    if rc != 0:
        return None, []
    rc2, names, _ = run_git(["diff", "--name-only"] + spec_args)
    return out, (names.splitlines() if rc2 == 0 else [])


def split_diff_blocks(diff):
    """按 diff 文件头切块，返回 [(b/path 或 None, 块文本)]。"""
    blocks, cur, cur_name = [], "", None
    for line in diff.splitlines(keepends=True):
        if line.startswith(("--- ", "+++ ", "diff --git ")):
            if line.startswith("+++ ") and cur is not None:
                m = re.match(r"\+\+\+ b/(.+)", line)
                if m:
                    cur_name = m.group(1).strip().strip('"')
            continue
        if line.startswith("diff --git "):
            if cur:
                blocks.append((cur_name, cur))
            cur, cur_name = "", None
            continue
        cur += line
    if cur:
        blocks.append((cur_name, cur))
    return blocks


def cmd_scan(args):
    # 确定扫描源
    if args.staged:
        diff, names = git_diff_text(["--cached"])
        label = "暂存区"
    elif args.range:
        diff, names = git_diff_text([args.range])
        if diff is None and diff != "":
            # range 不存在（首次推送），扫 HEAD
            rc, diff, _ = run_git(["show", "HEAD"])
            names = [os.path.basename(args.range or "HEAD")]
        label = f"范围 {args.range}"
    elif args.path:
        path = args.path
        if not os.path.exists(path):
            log(f"文件不存在: {path}", "FAIL")
            return 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            log(f"无法读取: {path}: {e}", "FAIL")
            return 1
        hits = scan_text(content, path)
        print(f"扫描: {path}")
        if hits:
            for name, seg in hits:
                log(f"疑似敏感内容 [{name}]: {seg}...", "FAIL")
            log("扫描未通过", "FAIL")
            return 1
        log("未发现敏感内容", "PASS")
        return 0
    else:
        # 默认：工作区已跟踪文件的改动 + 未跟踪文件
        rc, out, _ = run_git(["status", "--porcelain", "-uall"])
        diff = out or ""
        names = [l[3:].strip() for l in out.splitlines() if l.strip()] if rc == 0 else []
        label = "工作区"

    print(f"扫描目标: {label}")

    # 扫描 diff 块（带文件名归属）
    found = []
    for fname, block in split_diff_blocks(diff or ""):
        hits = scan_text(block, fname)
        for name, seg in hits:
            found.append((fname or "(未知文件)", name, seg))
    # 额外扫未跟踪文件的实际内容
    for name in names:
        if name and os.path.isfile(name):
            try:
                with open(name, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
            if not any(pat.search(content) for _, pat in SENSITIVE_PATTERNS):
                continue
            for pat_name, pat in SENSITIVE_PATTERNS:
                for m in pat.finditer(content):
                    seg = m.group(0)
                    if any(seg.startswith(w) for w in WHITELIST_PREFIXES):
                        continue
                    found.append((name, pat_name, seg[:40]))
                    break

    if found:
        print(f"发现 {len(found)} 处疑似敏感内容:")
        for fname, name, seg in found:
            log(f"{fname}: [{name}] {seg}...", "FAIL")
        log("扫描未通过——禁止提交/推送含密钥的内容", "FAIL")
        return 1
    log(f"未发现敏感内容（{label}）", "PASS")
    return 0


# ================= 4. git hooks 安装 =================
def _py_path():
    return sys.executable.replace("\\", "/")


def _script_path(name):
    p = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), name))
    return p.replace("\\", "/")


PRE_COMMIT = """#!/bin/sh
# === vibekit security hook (install_hooks.py 自动生成，勿手改) ===
# 提交前：检查点 B 核对 + 敏感内容扫描（最后防线）
PY="{py}"
SEC="{sec}"
CP="{cp}"

# 1. 边界核对：项目在用 vibekit 流程（有边界声明）时强制检查点 B
if [ -f ".vibe/boundary.json" ] && [ -f ".vibe/checkpoint.json" ]; then
  "$PY" "$CP" b --boundary .vibe/boundary.json >/dev/null 2>&1 || {{
    echo "[vibekit] 提交被拒绝: 检查点 B 未通过（改动与边界声明不一致）"
    echo "          运行: {py} {cp} b --boundary .vibe/boundary.json 查看详情"
    exit 1
  }}
fi

# 2. 敏感内容扫描
"$PY" "$SEC" scan --staged >/dev/null 2>&1 || {{
  echo "[vibekit] 提交被拒绝: 暂存内容含疑似密钥/敏感信息"
  echo "          运行: {py} {sec} scan --staged 查看详情"
  exit 1
}}
exit 0
"""

PRE_PUSH = """#!/bin/sh
# === vibekit security hook (install_hooks.py 自动生成，勿手改) ===
# 推送前：扫描待推送内容中的敏感信息（最后防线）
PY="{py}"
SEC="{sec}"

"$PY" "$SEC" scan --range "refs/remotes/origin/main..HEAD" >/dev/null 2>&1 || {{
  echo "[vibekit] 推送被拒绝: 待推送内容含疑似密钥/敏感信息"
  echo "          运行: {py} {sec} scan --range refs/remotes/origin/main..HEAD 查看详情"
  exit 1
}}
exit 0
"""


def cmd_install_hooks(args):
    if not os.path.isdir(".git"):
        log("当前目录不是 git 仓库，无法安装 hooks", "FAIL")
        return 1
    hooks_dir = os.path.join(".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    targets = {"pre-commit": PRE_COMMIT, "pre-push": PRE_PUSH}
    for name, tmpl in targets.items():
        path = os.path.join(hooks_dir, name)
        if args.remove:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    head = f.read(120)
                if "vibekit security hook" in head:
                    os.remove(path)
                    log(f"已卸载 {name}", "INFO")
                else:
                    log(f"跳过 {name}（非 vibekit 生成的 hook，不动）", "WARN")
            continue
        content = tmpl.format(py=_py_path(), sec=_script_path("security.py"),
                              cp=_script_path("checkpoint.py"))
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"已安装 {name}（内容: 检查点B + 敏感扫描 / pre-push: 推送扫描）", "PASS")

    if args.remove:
        log("hooks 卸载完成", "INFO")
    else:
        log("hooks 安装完成。现在 git commit/push 会自动执行安全检查", "PASS")
    return 0


# ================= 5. 状态 =================
def cmd_status(args):
    print("vibekit 安全状态:")
    # hooks
    if os.path.isdir(".git/hooks"):
        for name in ("pre-commit", "pre-push"):
            path = os.path.join(".git", "hooks", name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    head = f.read(120)
                tag = "vibekit" if "vibekit security hook" in head else "其他来源"
                print(f"  {name}: 已安装（{tag}）")
            else:
                print(f"  {name}: 未安装")
    # 敏感文件存在性
    print("  敏感文件检查（工作区）:")
    for root, dirs, fnames in os.walk(".", topdown=True):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for fn in fnames:
            full = os.path.join(root, fn)
            if any(pat.search(full) for pat in SENSITIVE_PATH_PATTERNS):
                log(f"  ⚠ 发现敏感文件: {full}", "WARN")
    return 0


def main():
    parser = argparse.ArgumentParser(description="vibekit 安全模块")
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("check-command", help="危险命令检测")
    c.add_argument("command", help="要检查的命令字符串")

    c = sub.add_parser("check-path", help="敏感路径检测")
    c.add_argument("path", help="要检查的路径")

    c = sub.add_parser("scan", help="敏感内容扫描")
    c.add_argument("--staged", action="store_true", help="扫描暂存区")
    c.add_argument("--range", default="", help="扫描 git 范围 A..B")
    c.add_argument("--path", default="", help="扫描单个文件")

    c = sub.add_parser("install-hooks", help="安装 git hooks（pre-commit/pre-push）")
    c.add_argument("--remove", action="store_true", help="卸载 hooks")

    sub.add_parser("status", help="安全状态总览")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0

    handler = {
        "check-command": cmd_check_command,
        "check-path": cmd_check_path,
        "scan": cmd_scan,
        "install-hooks": cmd_install_hooks,
        "status": cmd_status,
    }[args.cmd]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
