from pathlib import Path

import pytest

from Api.assessment_methodology_publication import PACKAGE_DIR, load_verified_m2_package


@pytest.mark.unit
def test_m2_publication_loader_verifies_reviewed_package() -> None:
    package = load_verified_m2_package()
    assert package["methodology"]["methodology_version"] == "1.1"
    assert {agent["code"] for agent in package["agents"]} == {
        "indicator_communication",
        "indicator_teamwork",
        "indicator_creativity",
        "indicator_critical_thinking",
    }
    assert all(agent["runtime"]["mode"] == "universal_llm" for agent in package["agents"])


@pytest.mark.unit
def test_m2_publication_loader_rejects_changed_artifact(tmp_path: Path) -> None:
    copied = tmp_path / "1.1"
    copied.mkdir()
    for path in PACKAGE_DIR.iterdir():
        if path.is_file():
            (copied / path.name).write_bytes(path.read_bytes())
        elif path.name == "agents":
            (copied / "agents").mkdir()
            for agent in path.iterdir():
                (copied / "agents" / agent.name).write_bytes(agent.read_bytes())
    methodology = copied / "methodology.json"
    methodology.write_text(methodology.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_verified_m2_package(copied)
