"""Fail if frontend/openapi.json no longer matches the API.

    uv run python scripts/check_openapi.py         (in backend/; part of `just check-backend`)

Exports the schema into a temporary file with the same command as `just api-schema` and
compares it with the committed file. It changes nothing in the working tree, so it also
passes with an uncommitted, but current, openapi.json.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

COMMITTED = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def export_command(target: Path) -> list[str]:
    return [
        sys.executable,
        "manage.py",
        "export_openapi_schema",
        "--api",
        "apps.core.api.api",
        "--indent",
        "2",
        "--output",
        str(target),
    ]


def normalized(content: bytes) -> bytes:
    # A Windows checkout (core.autocrlf) has CRLF where the export writes LF.
    return content.replace(b"\r\n", b"\n")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "openapi.json"
        subprocess.run(export_command(target), check=True)
        current = normalized(target.read_bytes())
    if not COMMITTED.exists() or normalized(COMMITTED.read_bytes()) != current:
        message = "API changed: run `just api-types` and commit both files"
        print(message, file=sys.stderr)
        return 1
    print("openapi.json up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
