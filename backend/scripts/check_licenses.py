"""Fail if a production dependency has a strong copyleft license (GPL, AGPL, SSPL).

    uv run python scripts/check_licenses.py        (in backend/; part of `just check-backend`)

Installs only the production dependencies from uv.lock into a throwaway venv, reads
their licenses with pip-licenses and checks them. LGPL is fine: it doesn't bind an
application that merely uses the library (e.g. psycopg).
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Whole tokens only, so "LGPL" doesn't count as "GPL".
FORBIDDEN = re.compile(r"(?<![A-Za-z])(A?GPL|SSPL)(?=$|[^A-Za-z]|v\d)|GNU (Affero )?General Public", re.I)
LESSER = re.compile(r"LGPL|Lesser General Public|Library General Public", re.I)

# Packages whose metadata is wrong or ambiguous, after checking them by hand: the package
# name as key, the reason as value.
ALLOW: dict[str, str] = {
    # The CalDAV server, run inside the app (apps/core/caldav). GPL-3.0 may be combined with the
    # project's AGPL-3.0; no other copyleft dependency is wanted.
    "radicale": "CalDAV server, deliberate; GPL-3.0 is compatible with our AGPL-3.0",
}

# pip-licenses and what it brings along; not part of the app.
TOOLING = ["pip-licenses", "prettytable", "wcwidth"]


def production_licenses() -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "requirements.txt"
        venv = Path(tmp) / "venv"
        bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
        run = ["uv", "--quiet"]
        subprocess.run(
            [
                *run,
                "export",
                "--locked",
                "--no-dev",
                "--no-hashes",
                "--format",
                "requirements.txt",
                "-o",
                str(requirements),
            ],
            check=True,
        )
        subprocess.run([*run, "venv", str(venv)], check=True)
        subprocess.run(
            [*run, "pip", "install", "--python", str(venv), "-r", str(requirements), *TOOLING[:1]],
            check=True,
        )
        output = subprocess.run(
            [str(bin_dir / "pip-licenses"), "--format=json", "--ignore-packages", *TOOLING],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    licenses: list[dict[str, str]] = json.loads(output)
    return licenses


def main() -> int:
    bad = []
    for pkg in production_licenses():
        name, license_ = pkg["Name"], pkg.get("License", "")
        if name.lower() in ALLOW:
            continue
        if FORBIDDEN.search(license_) and not LESSER.search(license_):
            bad.append(f"{name} {pkg.get('Version', '')}: {license_}")
    for line in bad:
        print(f"forbidden license: {line}")
    if not bad:
        print("licenses ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
