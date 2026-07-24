from __future__ import annotations

from Api.database import ensure_core_schema, get_connection
from Api.mbti.prompts import FOLLOWUP_PROMPT, PAIR_EVALUATION_PROMPT, SUMMARY_PROMPT, SYSTEM_PROMPT
from Api.mbti_refinement_service import MbtiRefinementService


PROMPTS = (
    ("mbti.system", "MBTI: системная инструкция", SYSTEM_PROMPT),
    ("mbti.case_evaluation", "MBTI: оценка кейса", PAIR_EVALUATION_PROMPT),
    ("mbti.session_summary", "MBTI: итоговая сводка", SUMMARY_PROMPT),
    ("mbti.followup", "MBTI: уточняющие вопросы", FOLLOWUP_PROMPT),
    ("mbti.refinement", "MBTI: обновление сводки", MbtiRefinementService.REFINE_SUMMARY_PROMPT),
    (
        "mbti.refinement_system",
        "MBTI: системная инструкция уточнения",
        "Ты уточняешь уже существующую MBTI-сводку и возвращаешь только JSON.",
    ),
)


def main() -> None:
    ensure_core_schema()
    with get_connection() as connection:
        for prompt_code, prompt_name, prompt_text in PROMPTS:
            connection.execute(
                """
                INSERT INTO llm_prompts (prompt_code, prompt_name, prompt_text)
                VALUES (%s, %s, %s)
                ON CONFLICT (prompt_code) DO NOTHING
                """,
                (prompt_code, prompt_name, prompt_text.strip()),
            )
        connection.commit()
    print(f"Migrated {len(PROMPTS)} prompt records (existing records preserved).")


if __name__ == "__main__":
    main()
