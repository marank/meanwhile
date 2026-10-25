"""
Notification creation helper, and the emails that go out along with notifications.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.core.mail import EmailMultiAlternatives

from core.models import Calendar, Event, User
from core.models.events import Notification
from core.realtime import broadcast
from core.services import mail
from core.services.mail_texts import text
from core.services.unsubscribe import muted_user_ids

# Kinds of email users can switch on and off, and whether they get them unless they chose.
EMAIL_KINDS = {
    "invitations": True,  # invitations to events, their changes and cancellations
    "responses": True,  # participants' answers to the user's invitations
    "approvals": True,  # booking requests to decide and cancelled bookings
    "decisions": True,  # decisions on the user's bookings
    "comments": True,
    "memberships": True,  # added to a calendar
    "role_changes": False,  # more rights in a calendar
    "reminders": False,  # reminders pop up in the app already
}

# The kind of email each notification type goes out as; types not listed come in the app only
# (an invitation comes as iMIP email when sent, see core.services.itip).
EMAIL_KIND_OF = {
    "approval_requested": "approvals",
    "booking_cancelled": "approvals",
    "booking_approved": "decisions",
    "booking_rejected": "decisions",
    "comment_added": "comments",
    "member_added": "memberships",
    "member_role_changed": "role_changes",
    "participant_replied": "responses",
    "event_reminder": "reminders",
}


def email_preferences(user: User) -> dict[str, bool]:
    chosen = user.email_notifications or {}
    return {kind: bool(chosen.get(kind, default)) for kind, default in EMAIL_KINDS.items()}


def wants_email(user: User, kind: str) -> bool:
    return user.is_active and bool(user.email) and email_preferences(user)[kind]


def notify(
    recipient_ids: Iterable[str | None],
    type: str,
    actor_id: str | None,
    title: str,
    calendar_id: str | None = None,
    event_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    seen = [r for r in dict.fromkeys(recipient_ids) if r is not None and r != actor_id]
    Notification.objects.bulk_create(
        Notification(
            user_id=recipient_id,
            type=type,
            actor_id=actor_id,
            calendar_id=calendar_id,
            event_id=event_id,
            title=title,
            data=data,
        )
        for recipient_id in seen
    )
    # A bulk insert sends no signals (core.signals); the recipients' tabs update their notifications.
    for recipient_id in seen:
        broadcast.notifications_changed(recipient_id)

    kind = EMAIL_KIND_OF.get(type)
    # Fewer rights come in the app only: by email they would read like a reprimand.
    if type == "member_role_changed" and not (data or {}).get("promoted"):
        kind = None
    if kind is None or not seen:
        return
    event = Event.objects.filter(id=event_id).first() if event_id else None
    # Who asked for no more emails about this event (its series) gets it in the app only.
    muted = muted_user_ids(event) if event else set()
    recipients = [u for u in User.objects.filter(id__in=seen) if wants_email(u, kind) and str(u.id) not in muted]
    if not recipients:
        return
    actor = User.objects.filter(id=actor_id).first() if actor_id else None
    calendar = Calendar.objects.filter(id=calendar_id).first() if calendar_id else None
    app = mail.app_name()
    mail.send(_notification_email(user, type, actor, title, calendar, event, data or {}, app) for user in recipients)


# Event emails: how the coloured line on top of the event card looks, by type (None: no line).
_NOTICE_TONES: dict[str, mail.NoticeTone | None] = {
    "approval_requested": "warning",
    "booking_approved": "success",
    "booking_rejected": "danger",
    "booking_cancelled": "danger",
    "comment_added": "neutral",
    "participant_replied_accepted": "success",
    "participant_replied_tentative": "warning",
    "participant_replied_declined": "danger",
    "participant_replied_needs_action": "neutral",
    "event_reminder": None,
}
_BOOKINGS = {"approval_requested", "booking_approved", "booking_rejected", "booking_cancelled"}


def _notification_email(
    user: User,
    type: str,
    actor: User | None,
    title: str,
    calendar: Calendar | None,
    event: Event | None,
    data: dict[str, Any],
    app: str,
) -> EmailMultiAlternatives:
    language = mail.language_of(user)
    if actor is not None:
        actor_name = actor.display_name or actor.email
    else:
        actor_name = data.get("name") or data.get("email") or text(language, "someone")
    title = title or text(language, "untitled")
    values = {"actor": actor_name, "title": title}
    if "role" in data:
        values["role"] = text(language, f"role_{data['role']}")
    key = type if type != "participant_replied" else f"participant_replied_{data.get('status', 'accepted')}"
    subject = text(language, f"{key}_subject", **values)
    body = text(language, f"{key}_body", **values)
    kind = EMAIL_KIND_OF[type]
    footer: dict[str, Any] = {
        "reason": text(language, f"reason_{kind}", calendar=calendar.name if calendar else ""),
        "recipient": user,
        "kind": kind,
        # The series, as no more emails are wanted about it as a whole.
        "event": (event.parent or event) if event else None,
    }

    if type in ("member_added", "member_role_changed") and calendar is not None:
        url = mail.app_link(f"/calendar/{calendar.id}")
    else:
        url = mail.app_link("/notifications")
    label = text(language, "review_request" if type == "approval_requested" else "open", app=app)
    links = [mail.Link(label, url, primary=True)] if url else []

    if event is None or key not in _NOTICE_TONES:
        details = []
        if calendar is not None and type not in ("member_added", "member_role_changed"):
            details.append((text(language, "calendar"), calendar.name))
        if "role" in data:
            details.append((text(language, "your_role"), text(language, f"role_{data['role']}_description")))
        return mail.build_message(
            to=user.email,
            subject=subject,
            paragraphs=[body],
            language=language,
            details=details,
            links=links,
            from_name=actor.display_name if actor else None,
            app=app,
            **footer,
        )

    reader = mail.Reader.of(user, language, event.timezone)
    start, end = event.start, event.end
    if type == "event_reminder" and data.get("start"):
        # The occurrence reminded of, which in a series isn't the first.
        start = datetime.fromisoformat(data["start"])
        end = start + (event.end - event.start)
    rows: list[tuple[str, str]] = []
    if event.location:
        rows.append((text(language, "location"), event.location))
    if type in _BOOKINGS and event.resource is not None:
        rows.append((text(language, "resource"), event.resource.name))
    if type == "approval_requested" and actor is not None:
        rows.append((text(language, "requested_by"), f"{actor_name} <{actor.email}>"))
    if calendar is not None:
        rows.append((text(language, "calendar"), calendar.name))
    for field in ("note", "comment"):
        if data.get(field):
            rows.append((text(language, field), data[field]))
    tone = _NOTICE_TONES[key]
    card = mail.EventCard(
        kicker=text(language, f"{type}_kicker"),
        title=title,
        when=mail.when_parts(start, end, event.all_day, reader, text(language, "all_day")),
        rows=rows,
        description=event.description if type == "event_reminder" else "",
        notice=body if tone else "",
        notice_tone=tone or "neutral",
        struck=type == "booking_cancelled",
        view=links[0] if links else None,
    )
    return mail.build_message(
        to=user.email,
        subject=subject,
        paragraphs=[body],
        language=language,
        details=[(text(language, "when"), mail.format_when(start, end, event.all_day, reader)), *rows],
        links=links,
        from_name=actor.display_name if actor else None,
        app=app,
        card=card,
        **footer,
    )
