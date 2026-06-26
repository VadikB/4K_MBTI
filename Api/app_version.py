from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib


BASE_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = BASE_DIR / "pyproject.toml"


@lru_cache(maxsize=1)
def get_app_version() -> str:
    try:
        payload = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "0.0.0"
    except Exception:
        return "0.0.0"
    return str(payload.get("project", {}).get("version") or "0.0.0").strip() or "0.0.0"
