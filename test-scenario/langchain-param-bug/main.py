"""
七阶段验收测试：LangChain 参数丢失场景
=========================================

模拟项目真实遇到过的坑：用 LangChain 的 with_structured_output 做结构化输出时，
先 bind() 再 with_structured_output() 导致 extra_body（thinking disabled）参数丢失。

- verify.py  : 拦截实际请求 payload，断言 extra_body 是否真实传递
- main.py    : 正确用法的示例代码（修复后版本）

复现过程（详见 README.md 的七阶段记录）：
    阶段④ 先写"错误用法"：llm.bind(extra_body=...).with_structured_output(...)
    阶段⑤ 验证拦截：mock 拦截 payload → 断言 extra_body 存在 → 失败 ❌
    阶段⑥ 审查定位：bind 返回 RunnableBinding，其 kwargs 不会传给
           with_structured_output（__getattr__ 只合并 config）
    阶段④' 修复：改为显式传 kwargs 给 with_structured_output
    阶段⑤' 验证通过：payload 含 extra_body ✅

依赖：pip install langchain-openai langchain-core pydantic
"""
from pydantic import BaseModel, Field


class Person(BaseModel):
    """结构化输出模型。"""
    name: str = Field(description="姓名")
    age: int = Field(description="年龄")


def build_correct_chain(llm):
    """
    正确用法：模型参数显式传给 with_structured_output。

    这是修复后的版本。extra_body 作为 with_structured_output 的 kwargs
    透传到最终请求（langchain-openai 0.3.21+ 支持）。

    Args:
        llm: ChatOpenAI 实例（DeepSeek 或其他 OpenAI 兼容）。

    Returns:
        with_structured_output 后的可调用链。
    """
    return llm.with_structured_output(
        Person,
        method="function_calling",
        include_raw=True,
        extra_body={"thinking": {"type": "disabled"}},
    )
