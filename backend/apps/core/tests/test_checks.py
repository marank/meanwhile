"""
System check core.E001: UUID primary keys.
"""

from collections.abc import Iterator

import pytest
from django.apps import apps
from django.db import models

from apps.core.checks import INTEGER_KEYS, uuid_primary_keys


@pytest.fixture
def integer_model() -> Iterator[type[models.Model]]:
    class IntegerKeyed(models.Model):
        class Meta:
            app_label = "core"

    yield IntegerKeyed
    del apps.all_models["core"]["integerkeyed"]
    apps.clear_cache()


def test_the_apps_models_pass() -> None:
    assert uuid_primary_keys() == []


def test_the_exceptions_are_real_models_with_integer_keys() -> None:
    for label in INTEGER_KEYS:
        assert not isinstance(apps.get_model(label)._meta.pk, models.UUIDField)


def test_a_model_with_an_integer_key_is_an_error(integer_model: type[models.Model]) -> None:
    [error] = uuid_primary_keys()
    assert error.id == "core.E001"
    assert error.obj is integer_model


def test_only_the_core_app_is_checked(integer_model: type[models.Model]) -> None:
    assert uuid_primary_keys(app_configs=[apps.get_app_config("auth")]) == []
