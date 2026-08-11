# -*- coding: utf-8 -*-
"""
验证脚本：拦截实际请求 payload，断言 extra_body 正确传递。

这是七阶段流水线"验证"阶段的工具——不信任"代码看起来对"，
而是 mock 掉真实网络调用，检查发给 API 的请求体里到底有没有 extra_body。

用法：
    python verify.py

输出：
    [PASS] 正确用法：payload 含 extra_body -> {'thinking': {'type': 'disabled'}}
    [FAIL] 错误用法：extra_body 丢失（这正是要拦截的 bug）
"""
import sys
from unittest.mock import patch

from langchain_openai import ChatOpenAI
from main import build_correct_chain

captured = {}


class FakeCompletions:
    """假的 OpenAI 补全响应。"""
    def create(self, **kwargs):
        captured["payload"] = kwargs
        import types
        message = types.SimpleNamespace(
            content="{}", tool_calls=[], additional_kwargs={}, role="assistant"
        )
        choice = types.SimpleNamespace(
            message=message, finish_reason="stop", logprobs=None
        )
        resp = types.SimpleNamespace(
            choices=[choice], usage=None, model=kwargs.get("model", ""),
            id="test", system_fingerprint=None, service_tier=None,
        )
        resp.model_dump = lambda **kw: {
            "choices": [{"message": {"content": "{}", "role": "assistant"},
                         "finish_reason": "stop"}],
            "model": kwargs.get("model", ""), "id": "test", "usage": None,
        }
        return resp


class FakeRawResponse:
    """假的 with_raw_response（LangChain 的 _generate 用它）。"""
    def create(self, **kwargs):
        return self._go(kwargs)

    def parse(self, **kwargs):
        return self._go(captured.get("payload", kwargs))

    def _go(self, kwargs):
        fc = FakeCompletions()
        fc.create(**kwargs)
        resp = fc.create(**kwargs)
        resp.parse = lambda **kw: resp
        return resp


def test_correct_usage() -> bool:
    """验证正确用法：extra_body 应该出现在 payload 里。"""
    captured.clear()
    llm = ChatOpenAI(
        model="deepseek-v4-flash",
        api_key="sk-test",          # 测试用，不会真的发请求
        base_url="https://api.deepseek.com",
        timeout=10,
    )
    chain = build_correct_chain(llm)

    with patch.object(llm.root_client.chat.completions, "with_raw_response",
                      FakeRawResponse()):
        chain.invoke("提取张三 25岁")

    payload = captured.get("payload", {})
    ok = "extra_body" in payload and payload["extra_body"] == {
        "thinking": {"type": "disabled"}
    }
    print(f"[{'PASS' if ok else 'FAIL'}] 正确用法: "
          f"extra_body in payload = {'extra_body' in payload}")
    if ok:
        print(f"        extra_body = {payload['extra_body']}")
    else:
        print(f"        payload keys = {list(payload.keys())}")
    return ok


def test_wrong_usage() -> bool:
    """
    验证错误用法（对照）：bind() 再 with_structured_output() → 参数丢失。

    七阶段测试里这一步是"发现 bug"的关键：mock 拦截后断言失败，
    证明验证阶段能抓住这类框架调用错误。
    """
    captured.clear()
    llm = ChatOpenAI(
        model="deepseek-v4-flash",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        timeout=10,
    )
    # ❌ 错误用法：先 bind 再 with_structured_output
    llm2 = llm.bind(extra_body={"thinking": {"type": "disabled"}})
    chain = llm2.with_structured_output(
        __import__("main").Person, method="function_calling", include_raw=True,
    )

    with patch.object(llm.root_client.chat.completions, "with_raw_response",
                      FakeRawResponse()):
        chain.invoke("提取张三 25岁")

    payload = captured.get("payload", {})
    lost = "extra_body" not in payload
    print(f"[{'PASS' if lost else 'FAIL'}] 错误用法对照: "
          f"extra_body 丢失 = {lost}（预期丢失，证明 bug 可被拦截）")
    return lost


if __name__ == "__main__":
    print("=" * 60)
    print("七阶段验证：拦截 payload 检查 extra_body 传递")
    print("=" * 60)
    ok1 = test_correct_usage()
    ok2 = test_wrong_usage()
    print("-" * 60)
    if ok1 and ok2:
        print("结论：正确用法参数完整传递；错误用法参数丢失可被拦截")
        sys.exit(0)
    else:
        print("结论：验证未通过")
        sys.exit(1)
