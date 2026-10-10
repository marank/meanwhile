"""
User and user-related models.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models.base import default_weekend_days, new_uuid7


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra) -> "User":
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

    def create_user(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_admin", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    username = None
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )

    groups = models.ManyToManyField(
        "UserGroup",
        related_name="user_set",
        db_table="user_group_members",
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.display_name or self.email


class UserGroup(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_groups"

    def __str__(self) -> str:
        return self.name


class AppSettings(models.Model):
    id = models.IntegerField(primary_key=True, default=1)
    app_name = models.CharField(max_length=255, default="Calendar")
    logo_url = models.TextField(blank=True, null=True)
    favicon_url = models.TextField(blank=True, null=True)
    default_first_weekday = models.IntegerField(default=0)
    default_show_weekends = models.BooleanField(default=True)
    default_weekend_days = models.JSONField(default=default_weekend_days)
    default_show_week_numbers = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_settings"


class AppPassword(models.Model):
    id = models.CharField(
        primary_key=True, max_length=36, default=new_uuid7, editable=False
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="app_passwords"
    )
    label = models.CharField(max_length=255)
    password_hash = models.CharField(max_length=255)
    last_used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_passwords"


def get_or_create_app_settings() -> AppSettings:
    settings, _ = AppSettings.objects.get_or_create(id=1)
    return settings
