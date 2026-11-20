"""
Applies the iTIP messages in email files (.eml) or iCalendar files (.ics), e.g. answers saved
from a mail program; `-` reads one email from standard input (for a mail server's pipe).
"""

import sys
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.core.services.itip import process_email, process_itip


class Command(BaseCommand):
    help = "Applies iTIP messages (e.g. REPLY) from .eml or .ics files, or an email on stdin."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("files", nargs="+", help="Files to read; - for standard input.")
        parser.add_argument(
            "--trust-sender",
            action="store_true",
            help="Apply answers even if the email wasn't sent by the participant they are for.",
        )

    def handle(self, *args: Any, files: list[str], trust_sender: bool, **options: Any) -> None:
        for name in files:
            raw = sys.stdin.buffer.read() if name == "-" else Path(name).read_bytes()
            if name.lower().endswith(".ics"):
                # A bare iCalendar file says nothing about who sent it.
                results = process_itip(raw)
            else:
                results = process_email(raw, trust_sender=trust_sender)
            for line in results:
                self.stdout.write(f"{name}: {line}")
