"""Read-only published configuration references for the Telegram integration."""

from __future__ import annotations

from Api.assessment_configuration import definition_checksum


def list_published_configurations(connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT configuration.id, configuration.code, configuration.name,
               configuration.methodology_version_id,
               configuration.scenario_version_id,
               configuration.catalog_version_id,
               configuration.prompt_bundle_checksum,
               configuration.is_default,
               methodology.code AS methodology_code,
               methodology_version.version AS methodology_version
        FROM assessment_configurations configuration
        JOIN assessment_methodology_versions methodology_version
          ON methodology_version.id = configuration.methodology_version_id
        JOIN assessment_methodologies methodology
          ON methodology.id = methodology_version.methodology_id
        JOIN assessment_scenario_versions scenario_version
          ON scenario_version.id = configuration.scenario_version_id
        WHERE configuration.status = 'published'
          AND methodology_version.status = 'published'
          AND scenario_version.status = 'published'
        ORDER BY configuration.code, configuration.id
        """
    ).fetchall()
    options = []
    for row in rows:
        reference = {
            "schema_version": 1,
            "id": int(row["id"]),
            "code": str(row["code"]),
            "methodology_version_id": int(row["methodology_version_id"]),
            "scenario_version_id": int(row["scenario_version_id"]),
            "catalog_version_id": (
                int(row["catalog_version_id"]) if row["catalog_version_id"] is not None else None
            ),
            "prompt_bundle_checksum": str(row["prompt_bundle_checksum"] or ""),
        }
        options.append(
            {
                "id": reference["id"],
                "ref": f"agent4k:configuration:{reference['id']}",
                "code": reference["code"],
                "name": str(row["name"]),
                "methodology_ref": (
                    f"agent4k:methodology:{row['methodology_code']}:v{row['methodology_version']}"
                ),
                "reference_checksum": definition_checksum(reference),
                "is_default": bool(row["is_default"]),
            }
        )
    return options
