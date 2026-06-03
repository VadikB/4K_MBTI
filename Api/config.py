from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "app_db")
    db_user: str = os.getenv("DB_USER", "app_user")
    db_password: str = os.getenv("DB_PASSWORD", "")
    log_level: str = (os.getenv("LOG_LEVEL", "INFO").strip() or "INFO").upper()
    log_to_stdout: bool = os.getenv("LOG_TO_STDOUT", "true").strip().lower() in {"1", "true", "yes", "on"}
    log_to_file: bool = os.getenv("LOG_TO_FILE", "false").strip().lower() in {"1", "true", "yes", "on"}
    log_dir: str = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
    log_filename: str = os.getenv("LOG_FILENAME", "agent4k.log")
    log_error_filename: str = os.getenv("LOG_ERROR_FILENAME", "agent4k-error.log")
    log_rotation_when: str = os.getenv("LOG_ROTATION_WHEN", "midnight").strip().lower() or "midnight"
    log_backup_count: int = int(os.getenv("LOG_BACKUP_COUNT", "14"))
    audit_logs_to_db: bool = os.getenv("AUDIT_LOGS_TO_DB", "true").strip().lower() in {"1", "true", "yes", "on"}
    runtime_logs_to_db: bool = os.getenv("RUNTIME_LOGS_TO_DB", "false").strip().lower() in {"1", "true", "yes", "on"}
    app_base_url: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8010").strip() or "http://127.0.0.1:8010"
    auth_magic_link_ttl_minutes: int = int(os.getenv("AUTH_MAGIC_LINK_TTL_MINUTES", "15"))
    auth_magic_link_dev_mode: bool = os.getenv("AUTH_MAGIC_LINK_DEV_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
    auth_magic_link_from_email: str = os.getenv("AUTH_MAGIC_LINK_FROM_EMAIL", "no-reply@agent4k.local").strip() or "no-reply@agent4k.local"
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_api_key_2: str = os.getenv("DEEPSEEK_API_KEY_2", "")
    deepseek_api_key_3: str = os.getenv("DEEPSEEK_API_KEY_3", "")
    deepseek_api_keys_raw: str = os.getenv("DEEPSEEK_API_KEYS", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    mbti_enabled: bool = os.getenv("MBTI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    mbti_faiss_index_dir: str = os.getenv("MBTI_FAISS_INDEX_DIR", "")
    mbti_top_k: int = int(os.getenv("MBTI_TOP_K", "5"))
    mbti_followup_mode: str = os.getenv("MBTI_FOLLOWUP_MODE", "assist").strip().lower() or "assist"
    mbti_followup_max_per_case: int = int(os.getenv("MBTI_FOLLOWUP_MAX_PER_CASE", "2"))
    mbti_followup_score_threshold: int = int(os.getenv("MBTI_FOLLOWUP_SCORE_THRESHOLD", "60"))
    mbti_refinement_target_confidence: int = int(os.getenv("MBTI_REFINEMENT_TARGET_CONFIDENCE", "75"))
    mbti_refinement_max_questions: int = int(os.getenv("MBTI_REFINEMENT_MAX_QUESTIONS", "6"))
    esco_api_enabled: bool = os.getenv("ESCO_API_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    esco_api_base_url: str = os.getenv("ESCO_API_BASE_URL", "https://ec.europa.eu/esco/api")
    esco_api_version: str = os.getenv("ESCO_API_VERSION", "v1.2.0")
    esco_api_language: str = os.getenv("ESCO_API_LANGUAGE", "en")

    @property
    def deepseek_api_keys(self) -> list[str]:
        values: list[str] = []
        for key in (self.deepseek_api_key, self.deepseek_api_key_2, self.deepseek_api_key_3):
            cleaned = str(key or "").strip()
            if cleaned and cleaned not in values:
                values.append(cleaned)
        raw_pool = str(self.deepseek_api_keys_raw or "").strip()
        if raw_pool:
            for item in raw_pool.split(","):
                cleaned = item.strip()
                if cleaned and cleaned not in values:
                    values.append(cleaned)
        return values

settings = Settings()
