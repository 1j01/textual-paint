"""Extract SVGs from Amber snapshot files, in order to view baselines."""

import re
from pathlib import Path

AMBR_DIR = Path(__file__).parent / "__snapshots__"
SVG_DIR = AMBR_DIR / "svg"
AMBR_FILE = AMBR_DIR / "test_snapshots.ambr"

# ensure directory exists
SVG_DIR.mkdir(parents=True, exist_ok=True)

re_snapshot = re.compile(r"^# name: (test_.*)\n  '''\n((?:.|\n  )*)\n  '''$", re.MULTILINE)

names: set[str] = set()
with open(AMBR_FILE, "r", encoding="utf-8") as f:
    for match in re_snapshot.finditer(f.read()):
        name = match.group(1)
        snapshot = match.group(2)
        names.add(name)
        with open(SVG_DIR / f"{name}.svg", "w", encoding="utf-8") as svg_file:
            svg = re.sub(r"^  ", "", snapshot, flags=re.MULTILINE)
            svg_file.write(svg)

print(f"Wrote {len(names)} files from {AMBR_FILE} to {SVG_DIR}")
