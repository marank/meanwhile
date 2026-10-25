#!/usr/bin/env python3
"""
Brings a .env up to date with .env.example, keeping every value it sets.

The result follows .env.example: its sections, comments and order. Variables of the .env keep
their lines as they are (also when commented out there); variables it doesn't have yet are added
commented out, so nothing changes until you set them. Variables .env.example doesn't know
(renamed or gone) are kept at the end, for you to look at. Comments are those of .env.example;
your own are only in the old file, kept as .env.bak.

    python3 scripts/sync_env.py             # updates .env in the project root
    python3 scripts/sync_env.py --dry-run   # only shows what would change

Only the standard library, so it runs wherever the .env is, without the backend's environment.
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# KEY=value, also commented out ("# KEY=value") or with "export ".
ASSIGNMENT = re.compile(r"^(?P<comment>#\s*)?(?:export\s+)?(?P<key>[A-Z][A-Z0-9_]*)=")
UNKNOWN_HEADER = "# --- Not in .env.example (renamed or no longer used?) " + "-" * 40


@dataclass
class Result:
    text: str
    added: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)


def _assignments(text: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """The set and the commented-out variables of a .env (key: line; the last one wins, as when it
    is read), and all keys in the order they first appear."""
    active: dict[str, str] = {}
    commented: dict[str, str] = {}
    order: list[str] = []
    for line in text.splitlines():
        match = ASSIGNMENT.match(line.strip())
        if not match:
            continue
        key = match["key"]
        if key not in order:
            order.append(key)
        (commented if match["comment"] else active)[key] = line.rstrip()
    return active, commented, order


def merge(example: str, current: str) -> Result:
    active, commented, order = _assignments(current)
    result = Result("")
    lines: list[str] = []
    known: set[str] = set()
    for line in example.splitlines():
        match = ASSIGNMENT.match(line.strip())
        if not match:
            lines.append(line.rstrip())
            continue
        key = match["key"]
        known.add(key)
        if key in active:
            lines.append(active[key])
        elif key in commented:
            lines.append(commented[key])
        else:
            result.added.append(key)
            lines.append(line.rstrip() if match["comment"] else f"# {line.strip()}")

    leftover = [active.get(key) or commented[key] for key in order if key not in known]
    if leftover:
        result.unknown = [key for key in order if key not in known]
        while lines and not lines[-1]:
            lines.pop()
        lines += ["", UNKNOWN_HEADER, *leftover]
    result.text = "\n".join(lines).rstrip("\n") + "\n"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[1], formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--env", type=Path, default=ROOT / ".env", help="the .env to update (default: %(default)s)")
    parser.add_argument("--example", type=Path, default=ROOT / ".env.example", help="default: %(default)s")
    parser.add_argument("--dry-run", action="store_true", help="show the changes, write nothing")
    args = parser.parse_args(argv)

    if not args.env.is_file():
        print(f"{args.env} doesn't exist: copy {args.example} to it and fill it in.", file=sys.stderr)
        return 1
    current = args.env.read_text(encoding="utf-8")
    result = merge(args.example.read_text(encoding="utf-8"), current)

    if result.text == current:
        print(f"{args.env} is up to date.")
        return 0
    if args.dry_run:
        diff = difflib.unified_diff(
            current.splitlines(keepends=True), result.text.splitlines(keepends=True), str(args.env), "updated"
        )
        sys.stdout.writelines(diff)
    else:
        backup = args.env.with_name(args.env.name + ".bak")
        shutil.copy2(args.env, backup)
        args.env.write_text(result.text, encoding="utf-8")
        print(f"Updated {args.env}; the old one is {backup}. Your values are unchanged.")
    if result.added:
        print(f"New, commented out (defaults apply until you set them): {', '.join(result.added)}")
    if result.unknown:
        print(f"Not in .env.example, kept at the end (renamed or no longer used?): {', '.join(result.unknown)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
