"""
Django form used by allauth to collect extra signup fields.
"""

from django import forms
from django.http import HttpRequest

from core.models import User


class SignupForm(forms.Form):
    display_name = forms.CharField(max_length=255, required=True)

    def signup(self, request: HttpRequest, user: User) -> None:
        user.display_name = self.cleaned_data.get("display_name", "")
