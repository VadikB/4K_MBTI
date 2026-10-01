"""Versioned integrity checks for immutable runtime snapshots."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable


SNAPSHOT_MISSING = "SNAPSHOT_MISSING"
SNAPSHOT_INTEGRITY_FAILED = "SNAPSHOT_INTEGRITY_FAILED"
SNAPSHOT_DEPENDENCY_UNAVAILABLE = "SNAPSHOT_DEPENDENCY_UNAVAILABLE"
SNAPSHOT_FORMAT_UNSUPPORTED = "SNAPSHOT_FORMAT_UNSUPPORTED"
SNAPSHOT_OWNER_MISMATCH = "SNAPSHOT_OWNER_MISMATCH"
SNAPSHOT_COMPOSITION_MISMATCH = "SNAPSHOT_COMPOSITION_MISMATCH"

CANONICALIZATION = "canonical-json-v1"
CHECKSUM_ALGORITHM = "sha256"


def execution_snapshot_integrity() -> dict[str, str]:
    return {
        "format": "product-4k-execution-snapshot",
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "canonicalization": CANONICALIZATION,
        "payload_scope": "complete_snapshot_except_database_metadata",
    }


def bind_execution_snapshot(value: dict[str, Any], *, user_id: int) -> dict[str, Any]:
    frozen = deepcopy(value)
    integrity = dict(frozen.get("_integrity") or execution_snapshot_integrity())
    integrity["owner"] = {"type": "user", "id": str(user_id)}
    frozen["_integrity"] = integrity
    return frozen


@dataclass(slots=True)
class SnapshotIntegrityError(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return self.code


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def verify_snapshot(
    value: Any,
    expected_checksum: str | None,
    *,
    supported_schema_versions: Iterable[int] = (1,),
    expected_user_id: int | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or not expected_checksum:
        raise SnapshotIntegrityError(SNAPSHOT_MISSING, "Snapshot or checksum is missing.")
    schema_version = value.get("schema_version")
    if not isinstance(schema_version, int) or schema_version not in set(supported_schema_versions):
        raise SnapshotIntegrityError(
            SNAPSHOT_FORMAT_UNSUPPORTED,
            f"Unsupported snapshot schema_version: {schema_version!r}.",
        )
    integrity = value.get("_integrity")
    if (
        not isinstance(integrity, dict)
        or integrity.get("format") != "product-4k-execution-snapshot"
        or integrity.get("checksum_algorithm") != CHECKSUM_ALGORITHM
        or integrity.get("canonicalization") != CANONICALIZATION
        or integrity.get("payload_scope") != "complete_snapshot_except_database_metadata"
        or not isinstance(integrity.get("owner"), dict)
    ):
        raise SnapshotIntegrityError(SNAPSHOT_FORMAT_UNSUPPORTED, "Unsupported snapshot integrity format.")
    if snapshot_checksum(value) != expected_checksum:
        raise SnapshotIntegrityError(SNAPSHOT_INTEGRITY_FAILED, "Snapshot checksum does not match payload.")
    if expected_user_id is not None and integrity["owner"] != {"type": "user", "id": str(expected_user_id)}:
        raise SnapshotIntegrityError(SNAPSHOT_OWNER_MISMATCH, "Execution snapshot belongs to another user.")
    return dict(value)


def require_equal(actual: Any, expected: Any, *, owner: bool = False, detail: str) -> None:
    if actual != expected:
        raise SnapshotIntegrityError(
            SNAPSHOT_OWNER_MISMATCH if owner else SNAPSHOT_COMPOSITION_MISMATCH,
            detail,
        )
