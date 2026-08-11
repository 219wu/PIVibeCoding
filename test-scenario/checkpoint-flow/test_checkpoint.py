# -*- coding: utf-8 -*-
"""
checkpoint.py 回归测试：检查点 A/B/C 全流程（含 FAIL 路径）
============================================================

在临时 git 仓库中验证强制检查点工具的语义：
  A  干净 → PASS；非 git 目录 → FAIL(2)
  B  改动==边界 → PASS；动 untouched → FAIL；加未声明文件 → FAIL；漏改 → FAIL
  C  无 HEAD 无 stash → FAIL；有 HEAD → PASS

用法：python test_checkpoint.py
依赖：仅需 git + python3
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

CHECKPOINT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "skill", "vibekit", "scripts", "checkpoint.py"))

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


def run(args, cwd):
    r = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def git(args, cwd):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_repo(tmp):
    git(["init", "-q"], tmp)
    git(["config", "user.name", "t"], tmp)
    git(["config", "user.email", "t@t"], tmp)
    write(os.path.join(tmp, "a.txt"), "hello\n")
    write(os.path.join(tmp, "b.txt"), "b\n")
    write(os.path.join(tmp, "c.txt"), "c\n")
    git(["add", "-A"], tmp)
    git(["commit", "-q", "-m", "initial"], tmp)


def test_non_git_dir():
    print("[1] 非 git 目录：A 应 FAIL(2)")
    empty = tempfile.mkdtemp(prefix="cp-nogit-")  # 必须在 git 仓库之外
    try:
        rc, out, _ = run([CHECKPOINT, "a"], empty)
        check("非 git 目录 A 退出码 2", rc == 2, f"rc={rc}")
        check("非 git 目录提示 git init", "git init" in out)
    finally:
        shutil.rmtree(empty, ignore_errors=True)


def test_clean_flow(tmp):
    print("[2] 正常流程：A(干净) → 改文件 → B(通过) → C(通过)")
    rc, _, _ = run([CHECKPOINT, "a"], tmp)
    check("A 干净工作区 PASS(0)", rc == 0, f"rc={rc}")

    # 模拟任务改动：改 a.txt、新增 new.txt
    write(os.path.join(tmp, "a.txt"), "hello world\n")
    write(os.path.join(tmp, "new.txt"), "new\n")

    boundary = {"added": ["new.txt"], "modified": ["a.txt"],
                "untouched": ["c.txt"], "note": "test"}
    bpath = os.path.join(tmp, ".vibe", "boundary.json")
    with open(bpath, "w", encoding="utf-8") as f:
        json.dump(boundary, f, ensure_ascii=False, indent=2)

    rc, out, _ = run([CHECKPOINT, "b", "--boundary", ".vibe/boundary.json"], tmp)
    check("B 边界一致 PASS(0)", rc == 0 and "PASS" in out, f"rc={rc}\n{out}")

    rc, out, _ = run([CHECKPOINT, "c"], tmp)
    check("C 有 HEAD PASS(0)", rc == 0 and "PASS" in out, f"rc={rc}")


def test_violations(tmp):
    print("[3] 违规路径：B 应 FAIL(1) 且报错信息准确")
    # 恢复干净基线
    git(["checkout", "-q", "--", "."], tmp)
    rc, _, _ = run([CHECKPOINT, "a"], tmp)
    assert rc == 0

    write(os.path.join(tmp, "a.txt"), "hello world\n")
    write(os.path.join(tmp, "new.txt"), "new\n")
    boundary = {"added": ["new.txt"], "modified": ["a.txt"],
                "untouched": ["c.txt"], "note": "test"}
    bpath = os.path.join(tmp, ".vibe", "boundary.json")
    with open(bpath, "w", encoding="utf-8") as f:
        json.dump(boundary, f, ensure_ascii=False, indent=2)

    # 3a. 动了 untouched 的 c.txt
    write(os.path.join(tmp, "c.txt"), "touched!\n")
    rc, out, _ = run([CHECKPOINT, "b", "--boundary", ".vibe/boundary.json"], tmp)
    check("动 untouched → FAIL", rc != 0 and "不该动的文件" in out, f"rc={rc}")
    git(["checkout", "-q", "--", "c.txt"], tmp)

    # 3b. 加了未声明文件 d.txt（多改）
    write(os.path.join(tmp, "d.txt"), "extra\n")
    rc, out, _ = run([CHECKPOINT, "b", "--boundary", ".vibe/boundary.json"], tmp)
    check("加未声明文件（多改）→ FAIL", rc != 0 and "超出边界声明" in out, f"rc={rc}")
    os.remove(os.path.join(tmp, "d.txt"))

    # 3c. 漏改：边界声明了 new2.txt 但没创建
    b2 = {"added": ["new.txt", "new2.txt"], "modified": ["a.txt"],
          "untouched": ["c.txt"], "note": "test"}
    with open(bpath, "w", encoding="utf-8") as f:
        json.dump(b2, f, ensure_ascii=False, indent=2)
    rc, out, _ = run([CHECKPOINT, "b", "--boundary", ".vibe/boundary.json"], tmp)
    check("漏改（声明文件未实现）→ FAIL", rc != 0 and "漏改" in out, f"rc={rc}")

    # 3d. 修复后 B 通过（证明可恢复）
    write(os.path.join(tmp, "new2.txt"), "n2\n")
    rc, out, _ = run([CHECKPOINT, "b", "--boundary", ".vibe/boundary.json"], tmp)
    check("修复后 B PASS(0)", rc == 0 and "PASS" in out, f"rc={rc}")


def test_no_rollback(tmp):
    print("[4] 无回滚点：C 应 FAIL(1)（无 HEAD 无 stash）")
    empty = os.path.join(tmp, "empty")
    os.makedirs(empty)
    git(["init", "-q"], empty)
    rc, out, _ = run([CHECKPOINT, "c"], empty)
    check("无 HEAD 无 stash → C FAIL", rc != 0 and "没有回滚点" in out, f"rc={rc}")


def main():
    tmp = tempfile.mkdtemp(prefix="cp-test-")
    try:
        make_repo(tmp)
        test_non_git_dir()
        test_clean_flow(tmp)
        test_violations(tmp)
        test_no_rollback(tmp)
        print("=" * 50)
        print(f"结果: {passed} 通过, {failed} 失败")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
