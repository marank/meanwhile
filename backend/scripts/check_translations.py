"""
Fails when a backend text is untranslated, fuzzy, or loses or gains a {placeholder}.

Run after `manage.py makemessages`, which adds new texts from the code as untranslated:

    uv run python manage.py makemessages -l de --ignore=.venv
    uv run python scripts/check_translations.py

Part of `just check-backend` (and so CI).
"""

import pathlib
import re
import sys

import polib

PLACEHOLDER = re.compile(r"\{\w*\}")


def problems(path: pathlib.Path) -> list[str]:
    po = polib.pofile(str(path))
    found = [f"untranslated: {entry.msgid}" for entry in po.untranslated_entries()]
    found += [f"fuzzy: {entry.msgid}" for entry in po.fuzzy_entries()]
    found += [
        f"placeholders differ: {entry.msgid}"
        for entry in po.translated_entries()
        if sorted(PLACEHOLDER.findall(entry.msgid)) != sorted(PLACEHOLDER.findall(entry.msgstr))
    ]
    return [f"{path}: {problem}" for problem in found]


def main() -> int:
    paths = sorted(pathlib.Path(__file__).resolve().parent.parent.glob("locale/*/LC_MESSAGES/django.po"))
    found = [problem for path in paths for problem in problems(path)]
    print("\n".join(found) or f"translations complete ({len(paths)} language(s))")
    return 1 if found or not paths else 0


if __name__ == "__main__":
    sys.exit(main())
