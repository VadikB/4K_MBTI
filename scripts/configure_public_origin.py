"""Write only public deployment configuration; never inspect or rewrite .env."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Api.public_origin import validate_public_origin


def configure(root: Path, origin: str) -> str:
    normalized = validate_public_origin(origin, mode="public")
    payload = {"schema_version": 1, "mode": "public", "origin": normalized}
    path = root / ".public-origin.json"
    descriptor, temporary = tempfile.mkstemp(prefix=".public-origin-", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=True, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return normalized


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print("Configured public origin: " + configure(args.root, args.origin))
