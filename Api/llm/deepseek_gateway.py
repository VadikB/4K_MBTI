from __future__ import annotations

import json
import logging
import threading
import time
import zlib
from urllib import error, request

from Api.config import settings
from Api.database import pause_thread_connections_for_external_io
from Api.llm.contracts import LlmMessage


logger = logging.getLogger("agent4k.deepseek.gateway")


class DeepSeekGateway:
    def __init__(
        self,
        *,
        api_keys: list[str] | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_keys = list(settings.deepseek_api_keys if api_keys is None else api_keys)
        self.base_url = str(base_url or settings.deepseek_base_url).rstrip("/")
        self.model = str(model or settings.deepseek_model)
        self.request_slots = threading.BoundedSemaphore(max(1, settings.deepseek_max_concurrency))

    @property
    def enabled(self) -> bool:
        return bool(self.api_keys)

    def build_routing_key(self, routing_key: str | None, messages: list[LlmMessage]) -> str:
        if str(routing_key or "").strip():
            return str(routing_key).strip()
        try:
            serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        except Exception:
            serialized = repr(messages)
        return f"messages:{zlib.crc32(serialized.encode('utf-8'))}"

    def get_key_chain(self, routing_key: str | None, messages: list[LlmMessage]) -> list[str]:
        if not self.api_keys:
            return []
        key_basis = self.build_routing_key(routing_key, messages)
        start_index = zlib.crc32(key_basis.encode("utf-8")) % len(self.api_keys)
        return [self.api_keys[(start_index + offset) % len(self.api_keys)] for offset in range(len(self.api_keys))]

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        temperature: float = 0.3,
        timeout_seconds: int = 120,
        routing_key: str | None = None,
    ) -> str:
        if not self.enabled:
            raise RuntimeError("DeepSeek API key is not configured")

        paused_connection_count = pause_thread_connections_for_external_io()
        queue_started_at = time.perf_counter()
        slot_acquired = self.request_slots.acquire(timeout=max(0.1, settings.deepseek_queue_timeout_seconds))
        queue_wait_ms = round((time.perf_counter() - queue_started_at) * 1000, 2)
        if not slot_acquired:
            logger.warning(
                "DeepSeek concurrency queue timed out after %.2f ms (limit=%s)",
                queue_wait_ms,
                settings.deepseek_max_concurrency,
            )
            raise RuntimeError(
                "Сервис обработки ответов сейчас перегружен. Подождите немного и повторите отправку."
            )

        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
        ).encode("utf-8")
        last_error: Exception | None = None
        request_started_at = time.perf_counter()
        try:
            for api_key in self.get_key_chain(routing_key, messages):
                req = request.Request(
                    url=f"{self.base_url}/chat/completions",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    method="POST",
                )
                try:
                    with request.urlopen(req, timeout=timeout_seconds) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    logger.info(
                        "DeepSeek request completed duration_ms=%.2f queue_wait_ms=%.2f paused_db_connections=%s routing_key=%s",
                        (time.perf_counter() - request_started_at) * 1000,
                        queue_wait_ms,
                        paused_connection_count,
                        routing_key or "auto",
                    )
                    return str(body["choices"][0]["message"]["content"])
                except TimeoutError:
                    last_error = RuntimeError("DeepSeek request timed out")
                except error.HTTPError as exc:
                    last_error = RuntimeError(f"DeepSeek request failed with HTTP {exc.code}")
                except error.URLError as exc:
                    last_error = RuntimeError(f"DeepSeek request failed: {exc}")

            if last_error is not None:
                raise last_error
            raise RuntimeError("DeepSeek request failed: no available API keys")
        finally:
            self.request_slots.release()
