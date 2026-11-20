"""
System check core.E001: every model of the app has a UUID primary key (apps.core.models.base.UUIDModel,
or a one-to-one key to such a model), except the deliberate exceptions AGENTS.md names.
"""

from collections.abc import Sequence
from typing import Any

from django.apps import AppConfig, apps
from django.core import checks
from django.db import models

# The singleton and two internal log tables, never addressed by id from outside.
INTEGER_KEYS = frozenset({"core.AppSettings", "core.DeletedEvent", "core.ReminderDelivery"})


@checks.register(checks.Tags.models)
def uuid_primary_keys(app_configs: Sequence[AppConfig] | None = None, **kwargs: Any) -> list[checks.CheckMessage]:
    config = apps.get_app_config("core")
    if app_configs is not None and config not in app_configs:
        return []
    return [
        checks.Error(
            f"{model._meta.label} must use a UUID primary key.",
            hint="Inherit from apps.core.models.base.UUIDModel.",
            obj=model,
            id="core.E001",
        )
        for model in config.get_models()
        if model._meta.managed
        and not model._meta.proxy
        and model._meta.label not in INTEGER_KEYS
        and not _uuid_key(model._meta.pk)
    ]


def _uuid_key(field: models.Field[Any, Any] | None) -> bool:
    # A one-to-one extension of another model (OverviewSettings of a User) shares that model's key.
    target = getattr(field, "target_field", field) if field is not None and field.is_relation else field
    return isinstance(target, models.UUIDField)
