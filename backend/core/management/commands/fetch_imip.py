"""
Reads participants' answers to invitations (iTIP REPLY) from the iMIP mailbox, as the worker does
every five minutes (core.tasks). In development, `--mailpit` reads them from Mailpit instead.
"""

import json
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.services.itip import fetch_mailbox, process_email


def _mailpit(base: str, path: str, method: str = "GET", body: dict | None = None) -> bytes:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(f"{base.rstrip('/')}/api/v1{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=15) as response:
        return response.read()


def fetch_mailpit(base: str) -> list[str]:
    """The unread messages to the iMIP address in Mailpit, processed and then marked read."""
    query = "is:unread"
    if settings.IMIP_ADDRESS:
        query += f' to:"{settings.IMIP_ADDRESS}"'
    found = json.loads(_mailpit(base, f"/search?query={quote(query)}&limit=200"))
    ids = [m["ID"] for m in found.get("messages", [])]
    results = []
    for message_id in ids:
        results += process_email(_mailpit(base, f"/message/{message_id}/raw"))
    if ids:
        _mailpit(base, "/messages", "PUT", {"IDs": ids, "Read": True})
    return results


class Command(BaseCommand):
    help = "Applies participants' answers (iTIP REPLY) from the iMIP mailbox."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mailpit",
            metavar="URL",
            help="Development: read from Mailpit's API (e.g. http://localhost:8025) instead of IMAP.",
        )

    def handle(self, *args, **options):
        try:
            results = fetch_mailpit(options["mailpit"]) if options["mailpit"] else fetch_mailbox()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        for line in results:
            self.stdout.write(line)
        self.stdout.write(f"{len(results)} answer(s) processed")
