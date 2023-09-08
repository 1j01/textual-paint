"""Merge Amber snapshot files to include test results from both, and warn if shared results don't match.

This allows applying the TDD principle to snapshot tests, in the specific case that
tests can pass in isolation, but fail when run together.
"""

import re
from pathlib import Path

DIR = Path(__file__).parent / "__snapshots__"

files = [
    DIR / "test_snapshots.ambr",
    DIR / "test_snapshots_ascii.ambr",
]
output_file = DIR / "test_snapshots_merged.ambr"

re_snapshot = re.compile(r"^# name: (test_.*)\n  '''\n((?:.|\n  )*)\n  '''$", re.MULTILINE)

snapshots: dict[str, str] = {}
names: set[str] = set()
for file in files:
    with open(file, "r", encoding="utf-8") as f:
        for match in re_snapshot.finditer(f.read()):
            name = match.group(1)
            snapshot = match.group(2)
            if name in snapshots:
                if snapshots[name] != snapshot:
                    print(f"Snapshots don't match for {name}; preferring result from {files[0]}")
            else:
                snapshots[name] = snapshot
                names.add(name)

with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"# serializer version: 1\n")
    for name, snapshot in snapshots.items():
        f.write(f"# name: {name}\n  '''\n{snapshot}\n  '''\n# ---\n")

print(f"Merged {len(names)} snapshots from {len(files)} files into {output_file}")
