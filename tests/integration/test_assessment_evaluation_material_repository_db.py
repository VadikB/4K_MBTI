from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_evaluation_material_repository import AssessmentEvaluationMaterialRepository
from Api.assessment_evaluator_contracts import SkillEvaluationInput


TABLES = (
    "case_type_skill_evidence", "case_type_red_flags", "case_required_response_blocks",
    "session_case_messages", "case_texts", "case_response_artifacts", "case_type_passports",
    "cases_registry", "session_case_skills", "session_cases", "competency_skill_criteria",
    "competency_skills", "skills",
)


@pytest.fixture
def material_connection(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        for table in TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        connection.execute("CREATE TABLE skills (id BIGINT PRIMARY KEY, skill_code TEXT, skill_name TEXT, competency_name TEXT)")
        connection.execute("CREATE TABLE competency_skills (id BIGINT PRIMARY KEY, skill_code TEXT)")
        connection.execute(
            "CREATE TABLE competency_skill_criteria (competency_skill_id BIGINT, level_code TEXT, level_name TEXT, knowledge_text TEXT, skill_text TEXT, behavior_text TEXT)"
        )
        connection.execute("CREATE TABLE session_cases (id BIGINT PRIMARY KEY, session_id BIGINT, case_registry_id BIGINT)")
        connection.execute("CREATE TABLE session_case_skills (session_case_id BIGINT, skill_id BIGINT)")
        connection.execute("CREATE TABLE cases_registry (id BIGINT PRIMARY KEY, case_type_passport_id BIGINT)")
        connection.execute("CREATE TABLE case_type_passports (id BIGINT PRIMARY KEY, artifact_id BIGINT, base_structure_description TEXT)")
        connection.execute("CREATE TABLE case_response_artifacts (id BIGINT PRIMARY KEY, artifact_code TEXT, artifact_name TEXT)")
        connection.execute("CREATE TABLE case_texts (cases_registry_id BIGINT, constraints_text TEXT)")
        connection.execute("CREATE TABLE session_case_messages (id BIGINT PRIMARY KEY, session_case_id BIGINT, role TEXT, message_text TEXT)")
        connection.execute("CREATE TABLE case_required_response_blocks (case_type_passport_id BIGINT, block_code TEXT, block_name TEXT)")
        connection.execute("CREATE TABLE case_type_red_flags (case_type_passport_id BIGINT, flag_code TEXT, flag_name TEXT, flag_description TEXT)")
        connection.execute("CREATE TABLE case_type_skill_evidence (case_type_passport_id BIGINT, skill_id BIGINT, evidence_description TEXT, expected_signal TEXT)")
        connection.execute(
            """
            INSERT INTO skills VALUES
                (11, 'active_listening', 'Активное слушание', 'Коммуникация'),
                (12, 'brainstorming', 'Генерация идей', 'Креативность');
            INSERT INTO competency_skills VALUES (21, 'active_listening'), (22, 'brainstorming');
            INSERT INTO competency_skill_criteria VALUES
                (21, 'L1', 'Базовый', 'Понимает ожидания', 'Уточняет', 'Не предполагает');
            INSERT INTO session_cases VALUES (31, 42, 41);
            INSERT INTO session_case_skills VALUES (31, 11), (31, 12);
            INSERT INTO cases_registry VALUES (41, 51);
            INSERT INTO case_type_passports VALUES (51, 61, 'Вопрос и резюме');
            INSERT INTO case_response_artifacts VALUES (61, 'questions', 'Уточняющие вопросы');
            INSERT INTO case_texts VALUES (41, 'Не придумывать контекст');
            INSERT INTO session_case_messages VALUES
                (71, 31, 'user', 'Сначала уточню ожидаемый результат и срок.');
            INSERT INTO case_required_response_blocks VALUES (51, 'questions', 'Вопросы');
            INSERT INTO case_type_skill_evidence VALUES (51, 11, 'Уточняет ожидания', 'задает вопрос');
            """
        )
        yield connection
    with psycopg.connect(test_database_url) as connection:
        for table in TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


@pytest.mark.integration
def test_generic_material_repository_reads_only_frozen_skill_codes(material_connection) -> None:
    materials = AssessmentEvaluationMaterialRepository().load(
        material_connection,
        session_id=42,
        skill_codes=["active_listening"],
    )

    assert len(materials) == 1
    validated = SkillEvaluationInput.model_validate(materials[0])
    assert validated.skill_code == "active_listening"
    assert validated.cases[0].session_case_id == 31
    assert validated.cases[0].skill_evidence[0].expected_signal == "задает вопрос"
