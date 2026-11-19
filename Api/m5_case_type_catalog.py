"""Версионированный источник CaseType для импорта и выпуска банка M5."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from Api.assessment_case_contracts import VersionRef
from Api.xlsx_values import read_xlsx


CATALOG_ID = "m5-case-type-catalog"
CATALOG_VERSION = "1.0"
CATALOG_SHA256 = "d748e390933a45eabca44f305027f757c7568a6c4ef343ee5bc7f104c210b7c0"
CATALOG_DIR = (
    Path(__file__).resolve().parents[1]
    / "assessment_definitions/catalog_contracts/competencies_4k/case-types"
    / CATALOG_VERSION
)
SOURCE_NAME = "sources/M5_CaseType_Catalog_CT01-CT20_v1.0_FROZEN.xlsx"
SHEET = "CaseType Catalog"
HEADER = "CaseTypeID"


class M5CaseTypeCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CaseTypeCatalog:
    ref: VersionRef
    ids: frozenset[str]

    def validate(self, ids: list[str] | None, *, case_id: str, pointer: str) -> None:
        context = f"({case_id}); catalog {self.ref.id}@{self.ref.version}"
        if not isinstance(ids, list) or not ids:
            raise M5CaseTypeCatalogError(f"M5_CASE_TYPE_IDS_INVALID: {pointer} {context}")
        for index, value in enumerate(ids):
            if not isinstance(value, str) or value not in self.ids:
                raise M5CaseTypeCatalogError(
                    f"M5_CASE_TYPE_UNKNOWN: {value} at {pointer}/{index} {context}"
                )


def load_case_type_catalog() -> CaseTypeCatalog:
    label = f"{CATALOG_ID}@{CATALOG_VERSION}"
    manifest_path = CATALOG_DIR / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_bytes())
        if (manifest["schema_version"], manifest["id"], manifest["version"], manifest["status"]) != (
            1, CATALOG_ID, CATALOG_VERSION, "FROZEN",
        ):
            raise ValueError("wrong catalog identity")
        artifact, = manifest["artifacts"]
        if artifact["name"] != SOURCE_NAME or artifact["sha256"] != CATALOG_SHA256:
            raise ValueError("wrong source reference")
    except OSError as exc:
        raise M5CaseTypeCatalogError(f"M5_CASE_TYPE_CATALOG_UNAVAILABLE: {label} / {manifest_path.name}") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise M5CaseTypeCatalogError(f"M5_CASE_TYPE_CATALOG_MANIFEST_INVALID: {label}") from exc

    try:
        source = (CATALOG_DIR / SOURCE_NAME).read_bytes()
    except OSError as exc:
        raise M5CaseTypeCatalogError(f"M5_CASE_TYPE_CATALOG_UNAVAILABLE: {label} / {SOURCE_NAME}") from exc
    if hashlib.sha256(source).hexdigest() != CATALOG_SHA256:
        raise M5CaseTypeCatalogError(f"M5_CASE_TYPE_CATALOG_CHECKSUM_MISMATCH: {label} / {SOURCE_NAME}")

    try:
        rows = read_xlsx(source)[SHEET]
        header, = [column for column, value in rows[1]["cells"].items() if value == HEADER]
        ids = [row["cells"][header] for row in rows[2:]]
        if not ids or not all(isinstance(value, str) and re.fullmatch(r"CT\d{2}", value) for value in ids):
            raise ValueError("invalid CaseTypeID column")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate CaseTypeID")
    except (BadZipFile, IndexError, KeyError, ParseError, ValueError) as exc:
        raise M5CaseTypeCatalogError(f"M5_CASE_TYPE_CATALOG_CONTENT_INVALID: {label} / {SHEET}!{HEADER}") from exc
    ref = VersionRef(id=CATALOG_ID, version=CATALOG_VERSION, checksum=CATALOG_SHA256)
    return CaseTypeCatalog(ref=ref, ids=frozenset(ids))
