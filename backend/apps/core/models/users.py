"""
User and user-related models.
"""

from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from apps.core.models.base import TimestampedModel, UUIDModel, default_weekend_days


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username: str | None) -> User:
        # Email addresses are unique regardless of case (the constraint below), so sign-ins are too.
        return self.get(email__iexact=username)

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_admin", True)
        return self._create_user(email, password, **extra)


class User(UUIDModel, TimestampedModel, AbstractUser):
    # The stubs type username as a str field; removing it with None is how Django documents it.
    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255)
    is_admin = models.BooleanField(default=False)
    time_format = models.CharField(
        max_length=10,
        choices=[("auto", "auto"), ("24h", "24h"), ("12h", "12h")],
        default="auto",
    )
    date_format = models.CharField(
        max_length=10,
        choices=[("auto", "auto"), ("dmy", "dmy"), ("mdy", "mdy"), ("ymd", "ymd")],
        default="auto",
    )
    # IANA zone of the user's browser, kept current by the app; empty until first seen.
    # Times that clients send without a zone ("floating") are read in it.
    timezone = models.CharField(max_length=64, blank=True, default="")
    # Language of the app (settings.LANGUAGES), kept current by the app; emails are written in it.
    language = models.CharField(max_length=16, blank=True, default="")
    # Which kinds of notifications also come by email, by kind; missing kinds use the defaults.
    email_notifications = models.JSONField(default=dict, blank=True)

    # Replaces the auth Group relation of PermissionsMixin, which the stubs cannot express.
    groups: models.ManyToManyField[UserGroup, Any] = models.ManyToManyField(  # type: ignore[assignment]
        "UserGroup",
        related_name="user_set",
        db_table="user_group_members",
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    # The stubs expect django.contrib.auth's UserManager, whose username-based create_user this replaces.
    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        db_table = "users"
        constraints = [models.UniqueConstraint(Lower("email"), name="users_email_unique_ignoring_case")]

    def __str__(self) -> str:
        return self.display_name or self.email

    def save(self, *args: Any, **kwargs: Any) -> None:
        # One switch for the Django admin: superusers may sign in there (is_staff) and do everything.
        # Staff without being superuser could only sign in, as no permissions are given out.
        self.is_staff = self.is_superuser
        if kwargs.get("update_fields") is not None and "is_superuser" in kwargs["update_fields"]:
            kwargs["update_fields"] = {*kwargs["update_fields"], "is_staff"}
        super().save(*args, **kwargs)


class UserGroup(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "user_groups"

    def __str__(self) -> str:
        return self.name


class AppSettings(models.Model):
    id = models.IntegerField(primary_key=True, default=1)
    app_name = models.CharField(max_length=255, default="Meanwhile")
    logo_url = models.TextField(blank=True, default="")
    favicon_url = models.TextField(blank=True, default="")
    # Monday, as ISO 8601 and most of the world count; Sunday is 0.
    default_first_weekday = models.IntegerField(default=1)
    default_show_weekends = models.BooleanField(default=True)
    default_weekend_days = models.JSONField(default=default_weekend_days)
    default_show_week_numbers = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_settings"


class AppPassword(UUIDModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="app_passwords")
    label = models.CharField(max_length=255)
    # SHA-256 of the token (apps.core.services.app_passwords); the token itself is never kept.
    token_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_passwords"


def get_or_create_app_settings() -> AppSettings:
    settings, _ = AppSettings.objects.get_or_create(id=1)
    return settings
