"""
Fails when a backend text is untranslated, fuzzy, or loses or gains a {placeholder}.

Run after `manage.py makemessages`, which adds new texts from the code as untranslated:

    uv run python manage.py makemessages -l de -l de_Informal --ignore=.venv
    uv run python scripts/check_translations.py

A variant's catalogue (locale/de_Informal) holds only what differs from its language's (locale/de);
an empty entry there falls back to it. The informal German must translate every text the formal one
addresses the reader in ("Sie", "Ihr"), and say "du" in each.

Part of `just check-backend` (and so CI).
"""

import pathlib
import re
import sys

import polib

PLACEHOLDER = re.compile(r"\{\w*\}")
# Capitalized "Sie"/"Ihr…" in the formal German, and the informal one, which must not have them.
FORMAL_GERMAN = re.compile(r"\b(Sie|Ihnen|Ihre?[mnrs]?)\b")
FORMAL_ADDRESS = {"de_Informal": FORMAL_GERMAN}


def _texts(entry: polib.POEntry) -> list[str]:
    return [entry.msgstr, *entry.msgstr_plural.values()]


def _key(entry: polib.POEntry) -> tuple[str | None, str]:
    return entry.msgctxt, entry.msgid


def _variant_problems(po: polib.POFile, base: polib.POFile, formal: re.Pattern[str]) -> list[str]:
    addressing = {_key(entry) for entry in base if any(formal.search(text) for text in _texts(entry))}
    found = [
        f"untranslated, addresses the reader: {entry.msgid}"
        for entry in po.untranslated_entries()
        if _key(entry) in addressing
    ]
    found += [
        f"formal address: {entry.msgid}"
        for entry in po.translated_entries()
        if any(formal.search(text) for text in _texts(entry))
    ]
    return found


def problems(path: pathlib.Path) -> list[str]:
    po = polib.pofile(str(path))
    locale = path.parent.parent.name
    base_path = path.parents[2] / locale.partition("_")[0] / "LC_MESSAGES" / "django.po"
    variant = locale in FORMAL_ADDRESS
    found = [] if variant else [f"untranslated: {entry.msgid}" for entry in po.untranslated_entries()]
    if variant:
        found += _variant_problems(po, polib.pofile(str(base_path)), FORMAL_ADDRESS[locale])
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
