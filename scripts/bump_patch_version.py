"""Compatibility wrapper around the candidate-aware release operation."""

from __future__ import annotations

import sys

from prepare_release import main


if __name__ == "__main__":
    raise SystemExit(main(["patch", *sys.argv[1:]]))
