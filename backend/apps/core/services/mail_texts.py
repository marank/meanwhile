"""
Texts of the emails the app sends. English source strings; the translations live in
backend/locale/<language>/LC_MESSAGES/django.po (`manage.py makemessages`). Each email is written in
its recipient's language, whatever language the request that causes it runs in.
"""

from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import pgettext_lazy

# The context "email" keeps these apart from the same words elsewhere (e.g. in the Django admin).
TEXTS: dict[str, Promise] = {
    "sent_to": pgettext_lazy("email", "Sent to {email}."),
    "footer_settings_link": pgettext_lazy("email", "Email settings"),
    "footer_unsubscribe": pgettext_lazy("email", "Unsubscribe from these emails"),
    "footer_unsubscribe_kind": pgettext_lazy("email", "Unsubscribe from all emails of this kind"),
    "footer_mute_event": pgettext_lazy("email", "No more emails about this event"),
    "footer_home": pgettext_lazy("email", "Open {app}"),
    "reason_invitations": pgettext_lazy("email", "You get this email because {organizer} invited you to this event."),
    "reason_responses": pgettext_lazy("email", "You get this email because you organize this event."),
    "reason_approvals": pgettext_lazy(
        "email", 'You get this email because you approve bookings in the calendar "{calendar}".'
    ),
    "reason_decisions": pgettext_lazy("email", "You get this email because you asked for this booking."),
    "reason_comments": pgettext_lazy("email", "You get this email because you created or commented on this event."),
    "reason_memberships": pgettext_lazy(
        "email", 'You get this email because you were added to the calendar "{calendar}".'
    ),
    "reason_role_changes": pgettext_lazy(
        "email", 'You get this email because you are a member of the calendar "{calendar}".'
    ),
    "reason_reminders": pgettext_lazy("email", "You get this email because you set a reminder for this event."),
    "reason_account_invite": pgettext_lazy(
        "email", "You get this email because {actor} created an account for you in {app}."
    ),
    "reason_password_reset": pgettext_lazy(
        "email", "You get this email because a new password for {app} was requested for this address."
    ),
    "someone": pgettext_lazy("email", "Someone"),
    "untitled": pgettext_lazy("email", "Untitled event"),
    "open": pgettext_lazy("email", "Open in {app}"),
    "when": pgettext_lazy("email", "When"),
    "location": pgettext_lazy("email", "Where"),
    "calendar": pgettext_lazy("email", "Calendar"),
    "organizer": pgettext_lazy("email", "Organizer"),
    "description": pgettext_lazy("email", "Description"),
    "note": pgettext_lazy("email", "Note"),
    "comment": pgettext_lazy("email", "Comment"),
    "participants": pgettext_lazy("email", "Participants"),
    "role_owner": pgettext_lazy("email", "owner"),
    "role_manage": pgettext_lazy("email", "manage"),
    "role_full": pgettext_lazy("email", "all events"),
    "role_own": pgettext_lazy("email", "own events"),
    "role_read": pgettext_lazy("email", "read only"),
    "role_owner_description": pgettext_lazy("email", "All permissions, including deleting the calendar"),
    "role_manage_description": pgettext_lazy("email", "Can create and edit all events, and change settings and access"),
    "role_full_description": pgettext_lazy("email", "Can create and edit all events"),
    "role_own_description": pgettext_lazy("email", "Can create events, but only edit their own"),
    "role_read_description": pgettext_lazy("email", "Can view events"),
    "your_role": pgettext_lazy("email", "Your role"),
    "resource": pgettext_lazy("email", "Resource"),
    "requested_by": pgettext_lazy("email", "Requested by"),
    "review_request": pgettext_lazy("email", "Review request"),
    "approval_requested_kicker": pgettext_lazy("email", "Booking request"),
    "booking_approved_kicker": pgettext_lazy("email", "Your booking"),
    "booking_rejected_kicker": pgettext_lazy("email", "Your booking"),
    "booking_cancelled_kicker": pgettext_lazy("email", "Cancelled booking"),
    "comment_added_kicker": pgettext_lazy("email", "New comment"),
    "participant_replied_kicker": pgettext_lazy("email", "Answer to your invitation"),
    "event_reminder_kicker": pgettext_lazy("email", "Reminder"),
    # Notifications
    "approval_requested_subject": pgettext_lazy("email", "Approval requested: {title}"),
    "approval_requested_body": pgettext_lazy("email", '{actor} requested approval for "{title}".'),
    "booking_approved_subject": pgettext_lazy("email", "Booking approved: {title}"),
    "booking_approved_body": pgettext_lazy("email", '{actor} approved the booking "{title}".'),
    "booking_rejected_subject": pgettext_lazy("email", "Booking rejected: {title}"),
    "booking_rejected_body": pgettext_lazy("email", '{actor} rejected the booking "{title}".'),
    "booking_cancelled_subject": pgettext_lazy("email", "Booking cancelled: {title}"),
    "booking_cancelled_body": pgettext_lazy("email", '{actor} cancelled the booking "{title}".'),
    "comment_added_subject": pgettext_lazy("email", "New comment on {title}"),
    "comment_added_body": pgettext_lazy("email", '{actor} commented on "{title}".'),
    "member_added_subject": pgettext_lazy("email", "You were added to {title}"),
    "member_added_body": pgettext_lazy("email", '{actor} added you to the calendar "{title}".'),
    "member_role_changed_subject": pgettext_lazy("email", "Your rights in {title} changed"),
    "member_role_changed_body": pgettext_lazy("email", '{actor} changed your rights in the calendar "{title}".'),
    "event_reminder_subject": pgettext_lazy("email", "Reminder: {title}"),
    "event_reminder_body": pgettext_lazy("email", '"{title}" is coming up.'),
    "participant_replied_accepted_subject": pgettext_lazy("email", "Accepted: {title}"),
    "participant_replied_accepted_body": pgettext_lazy("email", '{actor} accepted your invitation to "{title}".'),
    "participant_replied_tentative_subject": pgettext_lazy("email", "Tentatively accepted: {title}"),
    "participant_replied_tentative_body": pgettext_lazy(
        "email", '{actor} tentatively accepted your invitation to "{title}".'
    ),
    "participant_replied_declined_subject": pgettext_lazy("email", "Declined: {title}"),
    "participant_replied_declined_body": pgettext_lazy("email", '{actor} declined your invitation to "{title}".'),
    "participant_replied_needs_action_subject": pgettext_lazy("email", "No answer yet: {title}"),
    "participant_replied_needs_action_body": pgettext_lazy("email", '{actor} took back their answer to "{title}".'),
    # Invitations by email, iMIP
    "invite_subject": pgettext_lazy("email", "Invitation: {title} @ {when}"),
    "invite_body": pgettext_lazy("email", '{organizer} invited you to "{title}".'),
    "update_subject": pgettext_lazy("email", "Updated invitation: {title} @ {when}"),
    "update_body": pgettext_lazy("email", '{organizer} changed "{title}".'),
    "cancel_subject": pgettext_lazy("email", "Cancelled: {title} @ {when}"),
    "cancel_body": pgettext_lazy("email", '{organizer} cancelled "{title}".'),
    "removed_body": pgettext_lazy("email", '{organizer} removed you from "{title}".'),
    "rsvp_prompt": pgettext_lazy(
        "email", "Will you attend? Answer in your mail program, or with one of the links below."
    ),
    "invite_kicker": pgettext_lazy("email", "Invitation from {organizer}"),
    "update_kicker": pgettext_lazy("email", "Updated invitation from {organizer}"),
    "cancel_kicker": pgettext_lazy("email", "Cancelled by {organizer}"),
    "removed_kicker": pgettext_lazy("email", "Invitation from {organizer}"),
    "your_answer": pgettext_lazy("email", "Your answer"),
    "answer_hint": pgettext_lazy("email", "You can also answer in your mail program."),
    "invited_as": pgettext_lazy("email", "Invited as {email}"),
    "all_day": pgettext_lazy("email", "All day"),
    "repeats": pgettext_lazy("email", "Repeats"),
    "repeats_DAILY": pgettext_lazy("email", "Daily"),
    "repeats_WEEKLY": pgettext_lazy("email", "Weekly"),
    "repeats_MONTHLY": pgettext_lazy("email", "Monthly"),
    "repeats_YEARLY": pgettext_lazy("email", "Yearly"),
    "view_event": pgettext_lazy("email", "View event"),
    "accept": pgettext_lazy("email", "Accept"),
    "tentative": pgettext_lazy("email", "Tentative"),
    "decline": pgettext_lazy("email", "Decline"),
    # Accounts created by an admin
    "account_invite_subject": pgettext_lazy("email", "You're invited to {app}"),
    "account_invite_heading": pgettext_lazy("email", "Hello {name}"),
    "account_invite_body": pgettext_lazy("email", "{actor} invited you to {app}."),
    "account_invite_choose_password": pgettext_lazy(
        "email",
        'To get started, set a password using the button below. For security, the link is only valid for a limited time; you can request a new one at any time with "Forgot your password?" on the sign-in page.',
    ),
    "account_invite_sign_in": pgettext_lazy(
        "email", "Sign in with this email address and the password you got from {actor}."
    ),
    "account_invite_email": pgettext_lazy("email", "Email"),
    "account_invite_set_password": pgettext_lazy("email", "Set password"),
    "account_invite_open": pgettext_lazy("email", "Sign in to {app}"),
    "password_reset_subject": pgettext_lazy("email", "Reset your password for {app}"),
    "password_reset_heading": pgettext_lazy("email", "Reset your password"),
    "password_reset_body": pgettext_lazy(
        "email",
        "Someone asked to reset the password of your account in {app}. Choose a new one using the button below.",
    ),
    "password_reset_validity": pgettext_lazy(
        "email",
        "For security, the link is only valid for a limited time and works once. If you didn't ask for this, ignore this email; your password stays as it is.",
    ),
    "password_reset_button": pgettext_lazy("email", "Choose new password"),
}


def text(language: str, key: str, **values: object) -> str:
    """The text in `language` (English where there is no translation), with `values` filled in."""
    with translation.override(language or "en"):
        return str(TEXTS[key]).format(**values)
