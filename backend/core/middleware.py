"""Response headers Django has no setting of its own for."""

from collections.abc import Callable

from django.http import HttpRequest
from django.http.response import HttpResponseBase

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
