from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
import zlib
from urllib import error, request

from Api.config import settings
from Api.database import pause_thread_connections_for_external_io
from Api.llm.contracts import LlmCapacityError, LlmGatewayError, LlmMessage, LlmResponse
from Api.llm.provider_contract import GATEWAY_VERSION, load_provider_contract


logger = logging.getLogger("agent4k.deepseek.gateway")


class OperationBudget:
    """Reserve a transport attempt before dispatch, including unknown outcomes."""
    def __init__(self, attempts, seconds):
        if not isinstance(attempts, int) or attempts < 1 or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("OPERATION_LIMITS_INVALID")
        self.limit = attempts
        self.used = 0
        self.deadline = time.monotonic() + seconds
        self.lock = threading.Lock()

    def remaining_seconds(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("OPERATION_DEADLINE_EXCEEDED")
        return remaining

    def reserve(self):
        with self.lock:
            remaining = self.remaining_seconds()
            if self.used >= self.limit:
                raise ValueError("OPERATION_ATTEMPT_LIMIT")
            self.used += 1
            return remaining


class DeepSeekGateway:
    def __init__(
        self,
        *,
        api_keys: list[str] | None = None,
        base_url: str | None = None,
        model: str | None = None,
        operation_max_attempts: int | None = None,
        operation_timeout_seconds: float = 600,
    ) -> None:
        self.api_keys = list(settings.deepseek_api_keys if api_keys is None else api_keys)
        self.base_url = str(base_url or settings.deepseek_base_url).rstrip("/")
        self.model = str(model or settings.deepseek_model)
        self.model_source = "explicit_operation" if model else "provider_contract"
        self.operation_max_attempts = operation_max_attempts if operation_max_attempts is not None else max(1, 2 * len(self.api_keys))
        self.operation_timeout_seconds = operation_timeout_seconds
        self._operation_budgets = {}
        self._operation_lock = threading.Lock()
        self.request_slots = threading.BoundedSemaphore(max(1, settings.deepseek_max_concurrency))

    def operation_budget(self, operation_id):
        # This gateway is the existing operation/run context. Never renew an
        # exhausted entry; a new gateway/run owns an independent registry.
        with self._operation_lock:
            if operation_id not in self._operation_budgets:
                self._operation_budgets[operation_id] = OperationBudget(
                    self.operation_max_attempts, self.operation_timeout_seconds)
            return self._operation_budgets[operation_id]

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
        max_tokens: int | None = None,
        routing_key: str | None = None,
        thinking: dict[str, str] | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        return self.chat_with_trace(
            messages, temperature=temperature, timeout_seconds=timeout_seconds,
            max_tokens=max_tokens, routing_key=routing_key, thinking=thinking,
            response_format=response_format,
        ).content

    def chat_with_trace(
        self,
        messages: list[LlmMessage],
        *,
        temperature: float = 0.3,
        timeout_seconds: int = 120,
        max_tokens: int | None = None,
        routing_key: str | None = None,
        thinking: dict[str, str] | None = None,
        response_format: dict[str, str] | None = None,
        operation_budget: OperationBudget | None = None,
    ) -> LlmResponse:
        if os.getenv("AGENT4K_SYNTHETIC_ONLY") == "1":
            raise RuntimeError("SYNTHETIC_PROFILE_EXTERNAL_PROVIDER_FORBIDDEN")
        if not self.enabled:
            raise RuntimeError("DeepSeek API key is not configured")

        contract = load_provider_contract()
        thinking = dict(thinking or contract["thinking"])
        response_format = dict(response_format or {"type": "text"})
        if thinking.get("type") not in {"enabled", "disabled"}:
            raise ValueError("DEEPSEEK_THINKING_MODE_UNSUPPORTED")
        if response_format.get("type") not in contract["supported_response_formats"]:
            raise ValueError("DEEPSEEK_RESPONSE_FORMAT_UNSUPPORTED")

        paused_connection_count = pause_thread_connections_for_external_io()
        queue_started_at = time.perf_counter()
        queue_timeout = max(0.1, settings.deepseek_queue_timeout_seconds)
        if operation_budget is not None:
            queue_timeout = min(queue_timeout, operation_budget.remaining_seconds())
        slot_acquired = self.request_slots.acquire(timeout=queue_timeout)
        queue_wait_ms = round((time.perf_counter() - queue_started_at) * 1000, 2)
        if not slot_acquired:
            logger.warning(
                "DeepSeek concurrency queue timed out after %.2f ms (limit=%s)",
                queue_wait_ms,
                settings.deepseek_max_concurrency,
            )
            raise LlmCapacityError(
                "Сервис обработки ответов сейчас перегружен. Подождите немного и повторите отправку.",
                sent={}, provider={"transport_attempts": [], "queue_wait_ms": queue_wait_ms},
            )

        request_payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "thinking": thinking,
            "response_format": response_format,
        }
        if max_tokens is not None:
            request_payload["max_tokens"] = int(max_tokens)
        sent = {
            "provider": "deepseek",
            "endpoint": f"{self.base_url}/chat/completions",
            "model": self.model,
            "parameters": {"temperature": temperature, "timeout_seconds": timeout_seconds,
                           "max_tokens": max_tokens, "thinking": thinking,
                           "response_format": response_format},
            "messages": messages,
            "gateway_version": GATEWAY_VERSION,
            "contract": {"version": contract["version"], "checksum": contract["checksum"]},
        }
        payload = json.dumps(request_payload).encode("utf-8")
        last_error: Exception | None = None
        transport_attempts: list[dict[str, object]] = []
        request_started_at = time.perf_counter()
        try:
            for api_key in self.get_key_chain(routing_key, messages):
                attempt_started_at = time.perf_counter()
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
                    effective_timeout = timeout_seconds
                    if operation_budget is not None:
                        effective_timeout = min(timeout_seconds, operation_budget.reserve())
                    with request.urlopen(req, timeout=effective_timeout) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    logger.info(
                        "DeepSeek request completed duration_ms=%.2f queue_wait_ms=%.2f paused_db_connections=%s routing_key=%s",
                        (time.perf_counter() - request_started_at) * 1000,
                        queue_wait_ms,
                        paused_connection_count,
                        routing_key or "auto",
                    )
                    choice = body["choices"][0]
                    content = choice["message"].get("content")
                    if content is None or not str(content).strip():
                        transport_attempts.append({"attempt": len(transport_attempts) + 1,
                            "outcome": "empty_response",
                            "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2)})
                        raise LlmGatewayError("DeepSeek returned an empty response", sent=sent,
                                              provider={"transport_attempts": transport_attempts})
                    if choice.get("finish_reason") == "length":
                        transport_attempts.append({"attempt": len(transport_attempts) + 1,
                            "outcome": "truncated",
                            "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2)})
                        raise LlmGatewayError("DeepSeek response was truncated", sent=sent,
                                              provider={"transport_attempts": transport_attempts,
                                                        "finish_reason": "length", "usage": body.get("usage")})
                    transport_attempts.append({"attempt": len(transport_attempts) + 1,
                        "outcome": "completed",
                        "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2)})
                    return LlmResponse(
                        content=str(content),
                        sent=sent,
                        provider={
                            "request_id": body.get("id"), "model": body.get("model"),
                            "revision": body.get("system_fingerprint"),
                            "finish_reason": choice.get("finish_reason"), "usage": body.get("usage"),
                            "transport_attempts": transport_attempts,
                        },
                    )
                except TimeoutError:
                    last_error = RuntimeError("DeepSeek request timed out")
                    transport_attempts.append({"attempt": len(transport_attempts) + 1, "outcome": "timeout",
                                               "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2)})
                except error.HTTPError as exc:
                    last_error = RuntimeError(f"DeepSeek request failed with HTTP {exc.code}")
                    transport_attempts.append({"attempt": len(transport_attempts) + 1,
                                               "outcome": "http_error", "status": exc.code,
                                               "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2)})
                except error.URLError as exc:
                    last_error = RuntimeError(f"DeepSeek request failed: {exc}")
                    transport_attempts.append({"attempt": len(transport_attempts) + 1, "outcome": "network_error",
                                               "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2)})

            if last_error is not None:
                raise LlmGatewayError(str(last_error), sent=sent,
                                      provider={"transport_attempts": transport_attempts}) from last_error
            raise LlmGatewayError("DeepSeek request failed: no available API keys", sent=sent,
                                  provider={"transport_attempts": transport_attempts})
        finally:
            self.request_slots.release()

    def preflight(self, *, response_format: str = "text") -> dict[str, object]:
        contract = load_provider_contract()
        return {
            "ready": self.enabled and response_format in contract["supported_response_formats"],
            "secret_configured": self.enabled,
            "provider": "deepseek", "requested_model": self.model,
            "model_source": self.model_source,
            "endpoint": f"{self.base_url}/chat/completions",
            "response_format": response_format, "thinking": contract["thinking"],
            "gateway_version": GATEWAY_VERSION, "contract_version": contract["version"],
            "contract_checksum": contract["checksum"],
        }
