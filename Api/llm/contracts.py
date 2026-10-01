from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


class LlmMessage(TypedDict):
    role: str
    content: str


@dataclass(frozen=True)
class LlmResponse:
    content: str
    provider: dict[str, Any]
    sent: dict[str, Any]


class LlmGatewayError(RuntimeError):
    def __init__(self, message: str, *, sent: dict[str, Any], provider: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.sent = sent
        self.provider = provider or {}


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

    def chat_with_trace(self, messages: list[LlmMessage], **kwargs: Any) -> LlmResponse: ...
