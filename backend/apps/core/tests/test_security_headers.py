"""
Django's own responses (admin, API) carry the same security headers as what nginx serves, so the
posture is consistent across everything the app returns (ZAP flagged these missing on API
responses). nginx's copy lives in docker/security_headers.conf.
"""

import pytest
from django.test import Client

from apps.core.middleware import PERMISSIONS_POLICY

pytestmark = pytest.mark.django_db

# Every directive the policy pins; the frontend's nginx policy sets the same ones.
CSP_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
]


def test_an_api_response_carries_the_full_csp_and_permissions_policy(client: Client) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    # Enforced in production, report-only in DEBUG (the tests' setting); the directives are the same.
    csp = res.get("Content-Security-Policy") or res.get("Content-Security-Policy-Report-Only") or ""
    for directive in CSP_DIRECTIVES:
        assert directive in csp, f"missing from CSP: {directive!r}"
    assert res["Permissions-Policy"] == PERMISSIONS_POLICY
    assert res["Referrer-Policy"] == "same-origin"
    assert res["X-Content-Type-Options"] == "nosniff"
