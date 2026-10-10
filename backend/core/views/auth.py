"""
CSRF bootstrap endpoint for the SPA.

Login/register/logout/session are handled by allauth headless under
/api/auth/v1/auth/*. This endpoint only ensures the csrftoken cookie
is present before the first mutating request.
"""

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET


@require_GET
def csrf_view(request):
    # Reading the token forces Django to set the csrftoken cookie.
    get_token(request)
    return JsonResponse({"ok": True})
