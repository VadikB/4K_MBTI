"""Isolated Typst worker; parent owns the timeout and process group."""
from __future__ import annotations

import sys
from pathlib import Path

import typst

source, destination, root, fonts = map(Path, sys.argv[1:5])
result = typst.compile(str(source), root=str(root), font_paths=[str(fonts)], ignore_system_fonts=True)
destination.write_bytes(result)
