"""Response headers Django has no setting of its own for, and the language of the API's messages."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils import translation

# The same policy nginx sets for what it serves (docker/security_headers.conf); keep the two in
# step. On Django's own responses (admin, API) it is defence in depth — JSON has no browsing
# context — but keeps the header consistent across everything the app returns.
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


def permissions_policy(
    get_response: Callable[[HttpRequest], HttpResponseBase],
) -> Callable[[HttpRequest], HttpResponseBase]:
    def middleware(request: HttpRequest) -> HttpResponseBase:
        response = get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response

    return middleware


# The header the SPA names its interface language in (src/api/client.ts). Not Accept-Language: the
# browser's languages must not decide (settings.LANGUAGES), only the one the user chose in the app.
LANGUAGE_HEADER = "HTTP_X_LANGUAGE"


def request_language(
    get_response: Callable[[HttpRequest], HttpResponseBase],
) -> Callable[[HttpRequest], HttpResponseBase]:
    """Answers in the SPA's language: the API's own errors, Django's password rules, allauth."""
    supported = {code for code, _name in settings.LANGUAGES}

    def middleware(request: HttpRequest) -> HttpResponseBase:
        language = request.META.get(LANGUAGE_HEADER, "")
        if language not in supported:
            return get_response(request)
        with translation.override(language):
            return get_response(request)

    return middleware
