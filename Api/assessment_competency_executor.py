from __future__ import annotations

from typing import Any, Iterable

from Api.assessment_evaluator_contracts import (
    CompetencyEvaluationInput,
    CompetencyEvaluationOutput,
    LegacyCompetencyEvaluatorAdapter,
)
from Api.config import settings
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.universal_competency_evaluator import UniversalCompetencyEvaluator


class CompetencyEvaluatorExecutor:
    """Route a validated frozen definition to an explicit implementation."""

    def __init__(self, strategies: Iterable[Any], *, llm_gateway: Any | None = None) -> None:
        self._strategies = {
            (f"evaluation.{str(strategy.agent_code).strip()}", 1): strategy
            for strategy in strategies
            if str(getattr(strategy, "agent_code", "")).strip()
        }
        self._llm_gateway = llm_gateway

    def resolve_strategy(self, input_data: CompetencyEvaluationInput) -> Any:
        executor = input_data.agent_definition.executor
        return self.resolve_component(executor.code, executor.version)

    def resolve_component(self, code: str, version: int) -> Any:
        key = (code, version)
        strategy = self._strategies.get(key)
        if strategy is None:
            raise RuntimeError(f"Evaluator implementation is not available: {key[0]} v{key[1]}")
        return strategy

    def execute(self, *, connection: Any, input_data: CompetencyEvaluationInput) -> CompetencyEvaluationOutput:
        runtime_mode = str(input_data.agent_definition.runtime.get("mode") or "")
        if runtime_mode == "universal_llm":
            if not settings.assessment_universal_llm_enabled:
                raise RuntimeError("Universal competency evaluator is disabled by configuration.")
            gateway = self._llm_gateway or DeepSeekGateway()
            return UniversalCompetencyEvaluator(gateway).evaluate(input_data=input_data)
        if runtime_mode != "legacy_adapter":
            raise RuntimeError(f"Unsupported competency evaluator runtime mode: {runtime_mode!r}.")
        strategy = self.resolve_strategy(input_data)
        return LegacyCompetencyEvaluatorAdapter(strategy).evaluate(
            connection=connection,
            input_data=input_data,
        )
