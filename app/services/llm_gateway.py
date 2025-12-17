from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Protocol

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRequest:
    purpose: str
    system_prompt: str
    user_prompt: str
    temperature: float
    json_mode: bool
    timeout_ms: Optional[int] = None


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    latency_ms: int
    attempts: int
    used_fallback: bool


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, req: LLMRequest) -> str:
        ...


class OpenAICompatProvider:
    def __init__(
        self,
        *,
        name: str,
        api_key: Optional[str],
        base_url: Optional[str],
        model: str,
    ) -> None:
        self.name = name
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def generate(self, req: LLMRequest) -> str:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.user_prompt},
            ],
            temperature=req.temperature,
            response_format={"type": "json_object"} if req.json_mode else None,
        )
        return response.choices[0].message.content


class LLMTimeoutError(RuntimeError):
    pass


class LLMGateway:
    def __init__(self, *, providers: Dict[str, LLMProvider], default_route: List[str]) -> None:
        self.providers = providers
        self.default_route = default_route

    async def generate(self, req: LLMRequest, *, route: Optional[List[str]] = None) -> LLMResponse:
        route = route or self.default_route
        used_fallback = False
        attempts = 0
        last_err: Optional[Exception] = None

        for idx, provider_name in enumerate(route):
            attempts += 1
            provider = self.providers.get(provider_name)
            if provider is None:
                last_err = ValueError(f"Unknown provider: {provider_name}")
                continue

            t0 = time.perf_counter()
            try:
                if req.timeout_ms:
                    content = await asyncio.wait_for(provider.generate(req), timeout=req.timeout_ms / 1000)
                else:
                    content = await provider.generate(req)

                latency_ms = int((time.perf_counter() - t0) * 1000)
                if idx > 0:
                    used_fallback = True

                logger.info(
                    "LLM done purpose=%s provider=%s model=%s json_mode=%s sys_chars=%s user_chars=%s ms=%s attempts=%s fallback=%s",
                    req.purpose,
                    provider.name,
                    provider.model,
                    req.json_mode,
                    len(req.system_prompt),
                    len(req.user_prompt),
                    latency_ms,
                    attempts,
                    used_fallback,
                )

                return LLMResponse(
                    content=content,
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=latency_ms,
                    attempts=attempts,
                    used_fallback=used_fallback,
                )

            except asyncio.TimeoutError as exc:
                last_err = LLMTimeoutError(f"Timeout provider={provider_name} purpose={req.purpose}")
            except Exception as exc:
                last_err = exc

        assert last_err is not None
        raise last_err


@lru_cache
def get_llm_gateway() -> LLMGateway:
    settings = get_settings()
    providers: Dict[str, LLMProvider] = {
        "deepseek": OpenAICompatProvider(
            name="deepseek",
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        ),
        "openai": OpenAICompatProvider(
            name="openai",
            api_key=settings.openai_api_key,
            base_url=None,
            model="gpt-4o-mini",
        ),
    }
    default_route = [settings.llm_provider.lower()]
    return LLMGateway(providers=providers, default_route=default_route)
