"""
Emails about accounts: the invitation into the app of an account an admin created, and the link to
set a forgotten password.
"""

from allauth.account.adapter import get_adapter
from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str

from core.models import User
from core.services import mail
from core.services.mail_texts import text


def set_password_link(user: User) -> str:
    """The link of a forgotten password (allauth's key, ResetPasswordView): it works once, for
    PASSWORD_RESET_TIMEOUT, and not after the password is set."""
    key = f"{user_pk_to_url_str(user)}-{default_token_generator.make_token(user)}"
    url: str = get_adapter().get_reset_password_from_key_url(key)
    return f"{url}?invite=1"


def send_invitation(user: User, inviter: User) -> None:
    """Tells the user about their account. One without a password gets the link to choose it; one
    with a password set by the admin is told to sign in (the admin passes the password on)."""
    # A new account has no language yet; the admin's is the better guess than English.
    language = mail.language_of(user, fallback=mail.language_of(inviter))
    app = mail.app_name()
    inviter_name = inviter.display_name or inviter.email
    paragraphs = [text(language, "account_invite_body", actor=inviter_name, app=app)]
    if user.has_usable_password():
        paragraphs.append(text(language, "account_invite_sign_in", actor=inviter_name))
        url = mail.app_link("/login")
        label = text(language, "account_invite_open", app=app)
    else:
        paragraphs.append(text(language, "account_invite_choose_password"))
        url = set_password_link(user)
        label = text(language, "account_invite_set_password")
    mail.send(
        [
            mail.build_message(
                to=user.email,
                subject=text(language, "account_invite_subject", app=app),
                heading=text(language, "account_invite_heading", name=user.display_name or user.email),
                paragraphs=paragraphs,
                language=language,
                details=[(text(language, "account_invite_email"), user.email)],
                links=[mail.Link(label, url, primary=True)] if url else [],
                from_name=inviter_name,
                app=app,
            )
        ]
    )


def send_password_reset(user: User, url: str) -> None:
    """The link to set a forgotten password (allauth's, see AccountAdapter), in the style of the app's
    other emails rather than allauth's plain text."""
    language = mail.language_of(user)
    app = mail.app_name()
    mail.send(
        [
            mail.build_message(
                to=user.email,
                subject=text(language, "password_reset_subject", app=app),
                heading=text(language, "password_reset_heading"),
                paragraphs=[
                    text(language, "password_reset_body", app=app),
                    text(language, "password_reset_validity"),
                ],
                language=language,
                details=[(text(language, "account_invite_email"), user.email)],
                links=[mail.Link(text(language, "password_reset_button"), url, primary=True)],
                app=app,
            )
        ]
    )
