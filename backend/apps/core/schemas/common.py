"""
Shared building blocks of the schemas: the base class and the annotated field types.
"""

import uuid
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ninja import Field
from ninja import Schema as NinjaSchema
from pydantic import AfterValidator, BeforeValidator, ConfigDict, WithJsonSchema

from apps.core.services.recurrence import validate_rrule


class Schema(NinjaSchema):
    # The OpenAPI schema (and the frontend's types generated from it) marks response fields with a
    # default as always present, as they are; request fields with one stay optional.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


Weekday = Annotated[int, Field(ge=0, le=6)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


def _known_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        raise ValueError("Unknown time zone") from None
    return name


TimeZoneName = Annotated[str, AfterValidator(_known_zone)]

# Ids are UUIDs in the database and strings in the API; objects given to a response carry UUIDs.
Id = Annotated[
    str,
    BeforeValidator(lambda value: str(value) if isinstance(value, uuid.UUID) else value),
    WithJsonSchema({"type": "string", "format": "uuid"}),
]


def _single_address(value: str) -> str:
    # One plain address, as invitations are mailed to it: no names, lists or line breaks.
    try:
        validate_email(value)
    except ValidationError:
        raise ValueError("Not a valid email address") from None
    return value


EmailAddress = Annotated[str, Field(max_length=254), AfterValidator(_single_address)]
RRule = Annotated[str, AfterValidator(validate_rrule)]

# Text that clients may also send as null for "none"; it is stored as "".
Text = Annotated[
    str,
    BeforeValidator(lambda value: "" if value is None else value),
    WithJsonSchema({"anyOf": [{"type": "string"}, {"type": "null"}]}, mode="validation"),
]

TimeFormat = Literal["auto", "24h", "12h"]
DateFormat = Literal["auto", "dmy", "mdy", "ymd"]
# The roles a group or the public can be given; ownership is never granted.
GrantableRole = Literal["read", "own", "full", "manage"]
# Never "manage": managing the calendar is only for people it was granted to.
PublicRole = Literal["read", "own", "full"]


class OkOut(Schema):
    """The answer of endpoints that only do something, such as deleting."""

    ok: bool
