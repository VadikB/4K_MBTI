from Api.integration_assessment_configurations import list_published_configurations


def test_only_published_configurations_are_queried_and_fingerprinted() -> None:
    class Result:
        def fetchall(self):
            return [{
                "id": 17,
                "code": "standard",
                "name": "Стандартная",
                "methodology_version_id": 8,
                "scenario_version_id": 9,
                "catalog_version_id": 10,
                "prompt_bundle_checksum": "a" * 64,
                "is_default": True,
                "methodology_code": "m1",
                "methodology_version": 2,
            }]

    class Connection:
        def execute(self, query):
            assert "configuration.status = 'published'" in query
            assert "methodology_version.status = 'published'" in query
            assert "scenario_version.status = 'published'" in query
            return Result()

    options = list_published_configurations(Connection())
    assert len(options) == 1
    assert options[0]["id"] == 17
    assert options[0]["ref"] == "agent4k:configuration:17"
    assert options[0]["methodology_ref"] == "agent4k:methodology:m1:v2"
    assert len(options[0]["reference_checksum"]) == 64
