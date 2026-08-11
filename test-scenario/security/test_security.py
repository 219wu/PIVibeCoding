# -*- coding: utf-8 -*-
"""
security.py 回归测试：误报场景 + 真实密钥场景
=============================================

覆盖 2026-08-11 真实拦截中发现的问题：
  - Streamlit st.metric("Token 数", ...) 的 "Token:" 标签曾被误判为密钥（已修）
  - 真实密钥（password= 长值 / sk-xxx）必须仍被拦截

用法：python test_security.py
依赖：仅标准库 + git
"""
import os
import subprocess
import sys
import tempfile

SECURITY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "skill", "vibekit", "scripts", "security.py"))

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
    r = subprocess.run([sys.executable, SECURITY] + args, cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout


def write_tmp(content, suffix=".txt"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_check_command():
    print("[1] check-command")
    rc, out = run(["check-command", "git push --force origin main"], ".")
    check("强制推送 → FAIL(2)", rc == 2, f"rc={rc}")
    rc, out = run(["check-command", "git add -A && git commit -m 'x'"], ".")
    check("正常命令 → PASS(0)", rc == 0, f"rc={rc}")
    rc, out = run(["check-command", "rm -rf /"], ".")
    check("rm -rf / → FAIL(2)", rc == 2, f"rc={rc}")
    rc, out = run(["check-command", "git reset --hard"], ".")
    check("git reset --hard → 0（CONFIRM 级，不阻断）", rc == 0, f"rc={rc}")


def test_check_path():
    print("[2] check-path")
    rc, _ = run(["check-path", "C:/Users/x/.pi/agent/auth.json"], ".")
    check("auth.json → FAIL(2)", rc == 2, f"rc={rc}")
    rc, _ = run(["check-path", "C:/Users/x/project/src/main.py"], ".")
    check("普通源码 → PASS(0)", rc == 0, f"rc={rc}")
    rc, _ = run(["check-path", "C:/Users/x/project/secret.pem"], ".")
    check("私钥文件 → FAIL(2)", rc == 2, f"rc={rc}")


def test_scan():
    print("[3] scan 敏感内容")
    # 注意：测试密钥用运行时拼接（SECRET_SAMPLE），源文件不出现完整模式，
    # 否则 security.py 扫描自身测试样本时会被自举拦截（pre-commit 实战验证过）
    SECRET_SAMPLE = "sk-" + "abcdefghijklmnopqrstuvwxyz1234567890"
    PWD_SAMPLE = "abc123def456ghi789jkl"

    # 真实密钥必须拦
    real = write_tmp(f"api_key = {SECRET_SAMPLE}\n")
    rc, _ = run(["scan", "--path", real], ".")
    check("sk-xxx 真实密钥 → FAIL(1)", rc == 1, f"rc={rc}")
    os.remove(real)

    # 长口令必须拦
    pw = write_tmp(f"password={PWD_SAMPLE}\n")
    rc, _ = run(["scan", "--path", pw], ".")
    check("password= 长值 → FAIL(1)", rc == 1, f"rc={rc}")
    os.remove(pw)

    # 误报场景：Streamlit 标签不得误判
    st = write_tmp('st.metric("Token 数", f"{mem_stats.get(\'token_count\', 0):,}")\n'
                   'st.metric("成本", "$0.12")\n')
    rc, out = run(["scan", "--path", st], ".")
    check("Streamlit 标签 → PASS(0)", rc == 0, f"rc={rc}")
    os.remove(st)

    # sk-test 白名单
    wt = write_tmp("api_key=sk-test-fake-key-for-testing\n")
    rc, _ = run(["scan", "--path", wt], ".")
    check("sk-test 白名单 → PASS(0)", rc == 0, f"rc={rc}")
    os.remove(wt)


def main():
    test_check_command()
    test_check_path()
    test_scan()
    print("=" * 50)
    print(f"结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
