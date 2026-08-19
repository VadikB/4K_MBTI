from __future__ import annotations

from typing import Protocol, TypedDict


class LlmMessage(TypedDict):
    role: str
    content: str


class LlmGateway(Protocol):
    @property
    def enabled(self) -> bool: ...

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        temperature: float = 0.3,
        timeout_seconds: int = 120,
        routing_key: str | None = None,
    ) -> str: ...
