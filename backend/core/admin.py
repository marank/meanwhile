"""
Django admin registrations.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm

from core import models


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = models.User
        fields = "__all__"


@admin.register(models.User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    model = models.User
    list_display = ("email", "display_name", "is_admin", "is_staff", "is_superuser", "is_active")
    list_filter = ("is_admin", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "display_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("display_name", "first_name", "last_name")}),
        ("Permissions", {"fields": ("is_admin", "is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
        ("Preferences", {"fields": ("time_format", "date_format")}),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "password1", "password2", "is_admin", "is_staff", "is_superuser", "is_active"),
            },
        ),
    )


@admin.register(models.UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(models.Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_public", "created_at")
    list_filter = ("is_public",)
    search_fields = ("name",)


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "calendar", "start", "status")
    list_filter = ("status",)
    search_fields = ("title",)


admin.site.register(models.AppSettings)
admin.site.register(models.AppPassword)
admin.site.register(models.CalendarMember)
admin.site.register(models.CalendarGroup)
admin.site.register(models.CalendarApprover)
admin.site.register(models.Folder)
admin.site.register(models.Category)
admin.site.register(models.Resource)
admin.site.register(models.ResourceApprover)
admin.site.register(models.EventParticipant)
admin.site.register(models.EventComment)
admin.site.register(models.EventActivity)
admin.site.register(models.Notification)
