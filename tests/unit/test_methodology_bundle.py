import copy

import pytest

from scripts.export_methodology_bundle import _canonical
from scripts.import_methodology_bundle import _verify


@pytest.mark.unit
def test_methodology_bundle_checksum_is_verified() -> None:
    import hashlib

    payload = {
        "schema_version": 1,
        "methodology_code": "competencies_4k",
        "methodology_version": "1.0",
        "tables": [],
    }
    bundle = {**payload, "checksum": hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()}

    _verify(bundle)


@pytest.mark.unit
def test_methodology_bundle_rejects_changed_content() -> None:
    bundle = {
        "schema_version": 1,
        "methodology_code": "competencies_4k",
        "methodology_version": "1.0",
        "tables": [],
        "checksum": "invalid",
    }

    changed = copy.deepcopy(bundle)
    changed["tables"].append({"name": "roles"})
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        _verify(changed)
