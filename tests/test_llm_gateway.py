import asyncio

import pytest

from app.services.llm_gateway import LLMGateway, LLMRequest, LLMTimeoutError


pytestmark = pytest.mark.anyio


class StubProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str = "m",
        delay_s: float = 0.0,
        exc=None,
        content: str = "ok",
    ):
        self.name = name
        self.model = model
        self.delay_s = delay_s
        self.exc = exc
        self.content = content
        self.calls = 0

    async def generate(self, req: LLMRequest) -> str:
        self.calls += 1
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.exc:
            raise self.exc
        return self.content


async def test_llm_gateway_single_provider_success():
    provider = StubProvider(name="p1", content="hello")
    gw = LLMGateway(providers={"p1": provider}, default_route=["p1"])
    res = await gw.generate(
        LLMRequest(
            purpose="test",
            system_prompt="sys",
            user_prompt="user",
            temperature=0.0,
            json_mode=False,
        )
    )
    assert res.content == "hello"
    assert res.provider == "p1"
    assert res.attempts == 1
    assert res.used_fallback is False
    assert provider.calls == 1


async def test_llm_gateway_timeout_falls_back():
    slow = StubProvider(name="slow", delay_s=0.05)
    fast = StubProvider(name="fast", content="ok")
    gw = LLMGateway(providers={"slow": slow, "fast": fast}, default_route=["slow", "fast"])
    res = await gw.generate(
        LLMRequest(
            purpose="test",
            system_prompt="sys",
            user_prompt="user",
            temperature=0.0,
            json_mode=False,
            timeout_ms=1,
        )
    )
    assert res.content == "ok"
    assert res.provider == "fast"
    assert res.attempts == 2
    assert res.used_fallback is True


async def test_llm_gateway_all_providers_fail_raises():
    err = RuntimeError("boom")
    p1 = StubProvider(name="p1", exc=err)
    p2 = StubProvider(name="p2", exc=LLMTimeoutError("timeout"))
    gw = LLMGateway(providers={"p1": p1, "p2": p2}, default_route=["p1", "p2"])
    with pytest.raises(Exception):
        await gw.generate(
            LLMRequest(
                purpose="test",
                system_prompt="sys",
                user_prompt="user",
                temperature=0.0,
                json_mode=False,
                timeout_ms=1,
            )
        )
