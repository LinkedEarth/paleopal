#!/usr/bin/env python3
"""
check_package_releases.py — has Pyleoclim, PyLiPD or PyleoTUPS released a version newer than the
one PaleoPAL's references were built from?

    python backend/scripts/check_package_releases.py

Reads `package` and `version` from backend/references/*_api.json and the latest release from PyPI.
Prints one JSON object per package that needs its references rebuilt (nothing when all are current).
Used by .github/workflows/check-package-releases.yml, which opens an issue for each.

A release counts as newer than a development build of the same number: 1.3.2 is newer than
1.3.2b0 (built from main before the release).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from packaging.version import InvalidVersion, Version

_REFERENCES = Path(__file__).resolve().parents[1] / "references"
# What to rebuild when a package releases, in the words the issue uses.
_REBUILD = {
    "pyleoclim": ["backend/references/pyleoclim_api.json (scripts/build_api_reference.py pyleoclim)",
                  "backend/workflows/pyleoclim_parameters.json (scripts/build_pyleoclim_parameters.py)"],
    "pylipd": ["backend/references/pylipd_api.json (scripts/build_api_reference.py pylipd)"],
    "pyleotups": ["backend/references/pyleotups_api.json (scripts/build_api_reference.py pyleotups)"],
}


def latest_release(package: str) -> str:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=30) as reply:
        return json.load(reply)["info"]["version"]


def needs_rebuild(built: str | None, released: str) -> bool:
    try:
        return built is None or Version(released) > Version(built)
    except InvalidVersion:
        return released != built


def main() -> int:
    for path in sorted(_REFERENCES.glob("*_api.json")):
        reference = json.loads(path.read_text())
        package, built = reference["package"], reference.get("version")
        try:
            released = latest_release(package)
        except Exception as exc:  # PyPI unreachable: say so, but don't fail the others
            print(f"Couldn't check {package}: {exc}", file=sys.stderr)
            continue
        if needs_rebuild(built, released):
            print(json.dumps({"package": package, "released": released, "built": built,
                              "rebuild": _REBUILD.get(package, [path.relative_to(path.parents[2]).as_posix()])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
