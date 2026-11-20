"""
The Radicale WSGI application with the plugins of this app.
"""

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from typing import Any
from urllib.parse import unquote

from defusedxml import DefusedXmlException
from django.conf import settings
from radicale import httputils, types, xmlutils
from radicale.app import Application as RadicaleApplication
from radicale.config import load as load_config

from apps.core.caldav.request import request_scope
from apps.core.caldav.storage import Forbidden

_ADDRESS_SET = xmlutils.make_clark("C:calendar-user-address-set")
_ADDRESSBOOK_HOME = xmlutils.make_clark("CR:addressbook-home-set")
_HREF = xmlutils.make_clark("D:href")


def _without_addressbooks(dav: str) -> str:
    return ", ".join(part for part in dav.split(", ") if part != "addressbook")


class Application(RadicaleApplication):
    """Radicale serves calendars and address books; this app has calendars only, which its
    answers say: no "addressbook" class, no address book home (clients would offer contact sync)."""

    def __call__(self, environ: types.WSGIEnviron, start_response: types.WSGIStartResponse) -> Iterable[bytes]:
        def respond(status: str, headers: list[tuple[str, str]], *args: Any) -> object:
            headers = [(n, _without_addressbooks(v) if n.lower() == "dav" else v) for n, v in headers]
            return start_response(status, headers, *args)

        # Radicale builds the whole response before it returns it.
        with request_scope():
            return super().__call__(environ, respond)

    def _xml_response(self, xml_content: ET.Element, request_info: dict[str, Any]) -> bytes:
        for parent in xml_content.iter():
            for child in list(parent):
                if child.tag == _ADDRESSBOOK_HOME:
                    parent.remove(child)
                elif child.tag == _ADDRESS_SET:
                    _add_mailto(child)
        return super()._xml_response(xml_content, request_info)

    def _read_xml_request_body(self, environ: types.WSGIEnviron, request_info: dict[str, Any]) -> ET.Element | None:
        # XML with entities (which defusedxml refuses: billion laughs, XXE) is a bad request like
        # any other XML that doesn't parse, not a server error.
        try:
            return super()._read_xml_request_body(environ, request_info)
        except DefusedXmlException as exc:
            raise RuntimeError(f"Refused XML: {exc!r}") from exc

    # Radicale answers errors raised by the storage with 500, except for PUT; refused writes get 403.
    def do_DELETE(
        self,
        environ: types.WSGIEnviron,
        base_prefix: str,
        path: str,
        user: str,
        user_groups: set[str],
        request_info: dict[str, Any],
    ) -> types.WSGIResponse:
        try:
            return super().do_DELETE(environ, base_prefix, path, user, user_groups, request_info)
        except Forbidden:
            return httputils.FORBIDDEN

    def do_PROPPATCH(
        self,
        environ: types.WSGIEnviron,
        base_prefix: str,
        path: str,
        user: str,
        user_groups: set[str],
        request_info: dict[str, Any],
    ) -> types.WSGIResponse:
        try:
            return super().do_PROPPATCH(environ, base_prefix, path, user, user_groups, request_info)
        except Forbidden:
            return httputils.FORBIDDEN


def _add_mailto(address_set: ET.Element) -> None:
    """The user's addresses (RFC 6638): besides the principal's URL, the email address, by which
    clients recognize the user as ORGANIZER or ATTENDEE of an event."""
    for href in list(address_set):
        path = [segment for segment in (href.text or "").split("/") if segment]
        if href.tag == _HREF and path and "@" in unquote(path[-1]):
            mailto = address_set.makeelement(_HREF, {})
            mailto.text = f"mailto:{unquote(path[-1]).lower()}"
            address_set.insert(0, mailto)
            return


def create_application() -> Application:
    # Radicale's defaults only: not /etc/radicale/config, ~/.config/radicale/config or RADICALE_CONFIG,
    # which could switch on what this app doesn't expect (other plugins, sharing, ...).
    config = load_config([])
    config.update(
        {
            # Radicale waits this long before refusing a login, which slows guessing down.
            "auth": {"type": "apps.core.caldav.auth", "delay": str(settings.CALDAV_FAILED_LOGIN_DELAY)},
            "rights": {"type": "apps.core.caldav.rights"},
            "storage": {"type": "apps.core.caldav.storage"},
        },
        source="meanwhile-inline",
    )
    return Application(config)
