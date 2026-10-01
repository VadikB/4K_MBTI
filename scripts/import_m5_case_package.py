"""Проверка или транзакционный импорт M5 package в настроенную БД."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.database import get_connection
from Api.m5_storage import import_package_directory, package_readback
from scripts.build_m5_case_package import OUTPUT, verify_directory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, default=OUTPUT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    verification = verify_directory(args.package_dir)
    if not args.apply:
        print(json.dumps({"mode": "verify_only", "verification": verification}, ensure_ascii=False, indent=2))
        return
    with get_connection() as connection:
        result = import_package_directory(connection, args.package_dir)
        readback = package_readback(connection, result["package_db_id"])
        connection.commit()
    print(json.dumps({"mode": "apply", "result": result, "readback": readback}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
