from __future__ import annotations

import pytest

from Api.snapshot_integrity import (
    SNAPSHOT_FORMAT_UNSUPPORTED,
    SNAPSHOT_INTEGRITY_FAILED,
    SNAPSHOT_MISSING,
    SNAPSHOT_OWNER_MISMATCH,
    SnapshotIntegrityError,
    bind_execution_snapshot,
    execution_snapshot_integrity,
    require_equal,
    snapshot_checksum,
    verify_snapshot,
)


pytestmark = pytest.mark.unit


def test_verified_snapshot_accepts_canonical_payload() -> None:
    payload = bind_execution_snapshot({"schema_version": 1, "b": 2, "a": 1}, user_id=7)

    assert verify_snapshot(payload, snapshot_checksum(payload)) == payload


@pytest.mark.parametrize(
    ("payload", "digest", "code"),
    [
        (None, None, SNAPSHOT_MISSING),
        (bind_execution_snapshot({"schema_version": 1}, user_id=7), "0" * 64, SNAPSHOT_INTEGRITY_FAILED),
        ({"schema_version": 999}, "ignored", SNAPSHOT_FORMAT_UNSUPPORTED),
    ],
)
def test_verified_snapshot_rejects_unverifiable_input(payload, digest, code) -> None:
    with pytest.raises(SnapshotIntegrityError) as caught:
        verify_snapshot(payload, digest)

    assert caught.value.code == code
    assert str(caught.value) == code


def test_owner_mismatch_is_distinct_from_checksum_failure() -> None:
    with pytest.raises(SnapshotIntegrityError) as caught:
        require_equal("as-2", "as-1", owner=True, detail="wrong owner")

    assert caught.value.code == SNAPSHOT_OWNER_MISMATCH

    payload = bind_execution_snapshot({"schema_version": 1}, user_id=7)
    with pytest.raises(SnapshotIntegrityError) as verified:
        verify_snapshot(payload, snapshot_checksum(payload), expected_user_id=8)
    assert verified.value.code == SNAPSHOT_OWNER_MISMATCH


def test_unknown_integrity_format_does_not_fall_back_to_legacy() -> None:
    payload = {
        "schema_version": 1,
        "_integrity": {
            "format": "unknown",
            "checksum_algorithm": "sha256",
            "canonicalization": "canonical-json-v1",
            "payload_scope": "complete_snapshot_except_database_metadata",
        },
    }

    with pytest.raises(SnapshotIntegrityError) as caught:
        verify_snapshot(payload, snapshot_checksum(payload))

    assert caught.value.code == SNAPSHOT_FORMAT_UNSUPPORTED


def test_snapshot_without_integrity_envelope_is_not_adapted() -> None:
    payload = {"schema_version": 1, "legacy": True}

    with pytest.raises(SnapshotIntegrityError) as caught:
        verify_snapshot(payload, snapshot_checksum(payload))

    assert caught.value.code == SNAPSHOT_FORMAT_UNSUPPORTED
