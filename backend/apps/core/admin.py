"""
Django admin registrations.
"""

from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.core import models

if TYPE_CHECKING:
    from django.contrib.admin.options import _FieldsetSpec

admin.site.site_header = "Meanwhile"
admin.site.site_title = "Meanwhile"
admin.site.index_title = "Administration"

LIGHT_COLORS = ("base_color", "weekend_color", "today_color", "event_color", "border_color", "outer_border_color")
DARK_COLORS = tuple(f"dark_{name}" for name in LIGHT_COLORS)

APPEARANCE_FIELDSETS: _FieldsetSpec = (
    (_("Week layout"), {"fields": ("first_weekday", "show_weekends", "weekend_days", "show_week_numbers")}),
    (_("Colors (light)"), {"classes": ("collapse",), "fields": LIGHT_COLORS}),
    (_("Colors (dark)"), {"classes": ("collapse",), "fields": DARK_COLORS}),
)


class CustomUserChangeForm(UserChangeForm[models.User]):
    class Meta(UserChangeForm.Meta):
        model = models.User
        fields = "__all__"


@admin.register(models.User)
class CustomUserAdmin(UserAdmin[models.User]):
    form = CustomUserChangeForm
    model = models.User
    list_display = ("email", "display_name", "is_admin", "is_superuser", "is_active", "last_login")
    list_filter = ("is_admin", "is_superuser", "is_active", "groups")
    search_fields = ("email", "display_name", "first_name", "last_name")
    ordering = ("email",)
    filter_horizontal = ("groups",)
    readonly_fields = ("last_login", "date_joined", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("display_name", "first_name", "last_name")}),
        (
            _("Permissions"),
            {"fields": ("is_admin", "is_superuser", "is_active", "groups")},
        ),
        (
            _("Preferences"),
            {"fields": ("language", "timezone", "time_format", "date_format", "day_start", "email_notifications")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "password1",
                    "password2",
                    "is_admin",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(models.UserGroup)
class UserGroupAdmin(admin.ModelAdmin[models.UserGroup]):
    list_display = ("name", "description", "member_count", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet[models.UserGroup]:
        return super().get_queryset(request).prefetch_related("user_set")

    @admin.display(description=_("Members"))
    def member_count(self, obj: models.UserGroup) -> int:
        return len(obj.user_set.all())


@admin.register(models.AppSettings)
class AppSettingsAdmin(admin.ModelAdmin[models.AppSettings]):
    list_display = ("app_name", "updated_at")
    readonly_fields = ("updated_at",)
    fieldsets = (
        (_("Branding"), {"fields": ("app_name", "logo_url", "favicon_url")}),
        (
            _("Calendar defaults"),
            {
                "fields": (
                    "default_first_weekday",
                    "default_show_weekends",
                    "default_weekend_days",
                    "default_show_week_numbers",
                )
            },
        ),
        (None, {"fields": ("updated_at",)}),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        # A singleton: there is one row, created on demand.
        return not models.AppSettings.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj: models.AppSettings | None = None) -> bool:
        return False


@admin.register(models.AppPassword)
class AppPasswordAdmin(admin.ModelAdmin[models.AppPassword]):
    list_display = ("label", "user", "last_used_at", "created_at")
    list_select_related = ("user",)
    search_fields = ("label", "user__email", "user__display_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("token_hash", "last_used_at", "created_at")
    date_hierarchy = "created_at"


@admin.register(models.Folder)
class FolderAdmin(admin.ModelAdmin[models.Folder]):
    list_display = ("name", "user", "parent", "position")
    list_select_related = ("user", "parent")
    search_fields = ("name", "user__email")
    autocomplete_fields = ("user", "parent")


class CalendarMemberInline(admin.TabularInline[models.CalendarMember, models.Calendar]):
    model = models.CalendarMember
    extra = 0
    autocomplete_fields = ("user",)
    # Memberships from a group or a public calendar are kept by the app and have no role of their own.
    fields = ("user", "source", "role")
    readonly_fields = ("source",)


class CalendarGroupInline(admin.TabularInline[models.CalendarGroup, models.Calendar]):
    model = models.CalendarGroup
    extra = 0
    autocomplete_fields = ("group",)
    fields = ("group", "role")


class CalendarApproverInline(admin.TabularInline[models.CalendarApprover, models.Calendar]):
    model = models.CalendarApprover
    extra = 0
    autocomplete_fields = ("user",)


class CategoryInline(admin.TabularInline[models.Category, models.Calendar]):
    model = models.Category
    extra = 0
    fields = ("name", "color", "description")


@admin.register(models.Calendar)
class CalendarAdmin(admin.ModelAdmin[models.Calendar]):
    list_display = ("name", "owner", "is_public", "force_all_day", "created_at")
    list_select_related = ("owner",)
    list_filter = ("is_public", "force_all_day")
    search_fields = ("name", "description", "owner__email", "owner__display_name")
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = (CalendarMemberInline, CalendarGroupInline, CalendarApproverInline, CategoryInline)
    fieldsets = (
        (None, {"fields": ("name", "description", "owner", "force_all_day")}),
        (_("Sharing"), {"fields": ("is_public", "public_role")}),
        (_("CalDAV"), {"classes": ("collapse",), "fields": ("dav_name", "url_path")}),
        *APPEARANCE_FIELDSETS,
        (_("Dates"), {"fields": ("created_at", "updated_at")}),
    )


@admin.register(models.CalendarMember)
class CalendarMemberAdmin(admin.ModelAdmin[models.CalendarMember]):
    list_display = ("calendar", "user", "source", "role", "folder")
    list_select_related = ("calendar", "user", "folder")
    list_filter = ("source", "role")
    search_fields = ("calendar__name", "user__email", "user__display_name")
    autocomplete_fields = ("calendar", "user", "folder")


@admin.register(models.CalendarGroup)
class CalendarGroupAdmin(admin.ModelAdmin[models.CalendarGroup]):
    list_display = ("calendar", "group", "role", "created_at")
    list_select_related = ("calendar", "group")
    list_filter = ("role",)
    search_fields = ("calendar__name", "group__name")
    autocomplete_fields = ("calendar", "group")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.CalendarApprover)
class CalendarApproverAdmin(admin.ModelAdmin[models.CalendarApprover]):
    list_display = ("calendar", "user")
    list_select_related = ("calendar", "user")
    search_fields = ("calendar__name", "user__email", "user__display_name")
    autocomplete_fields = ("calendar", "user")


@admin.register(models.OverviewSettings)
class OverviewSettingsAdmin(admin.ModelAdmin[models.OverviewSettings]):
    list_display = ("user", "use_calendar_colors", "first_weekday", "show_weekends", "show_week_numbers")
    list_select_related = ("user",)
    search_fields = ("user__email", "user__display_name")
    autocomplete_fields = ("user",)
    fieldsets = (
        (None, {"fields": ("user", "use_calendar_colors")}),
        *APPEARANCE_FIELDSETS,
    )


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin[models.Category]):
    list_display = ("name", "calendar", "color")
    list_select_related = ("calendar",)
    search_fields = ("name", "calendar__name")
    autocomplete_fields = ("calendar",)
    readonly_fields = ("created_at", "updated_at")


class ResourceApproverInline(admin.TabularInline[models.ResourceApprover, models.Resource]):
    model = models.ResourceApprover
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(models.Resource)
class ResourceAdmin(admin.ModelAdmin[models.Resource]):
    list_display = ("name", "calendar", "is_location", "requires_approval", "is_active", "archived_at")
    list_select_related = ("calendar",)
    list_filter = ("is_location", "requires_approval", "is_active")
    search_fields = ("name", "description", "calendar__name")
    autocomplete_fields = ("calendar",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (ResourceApproverInline,)


@admin.register(models.ResourceApprover)
class ResourceApproverAdmin(admin.ModelAdmin[models.ResourceApprover]):
    list_display = ("resource", "user")
    list_select_related = ("resource", "user")
    search_fields = ("resource__name", "user__email", "user__display_name")
    autocomplete_fields = ("resource", "user")


class EventParticipantInline(admin.TabularInline[models.EventParticipant, models.Event]):
    model = models.EventParticipant
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("email", "user", "status")


class EventCommentInline(admin.TabularInline[models.EventComment, models.Event]):
    model = models.EventComment
    extra = 0
    autocomplete_fields = ("author",)
    fields = ("author", "body", "created_at")
    readonly_fields = ("created_at",)


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin[models.Event]):
    list_display = ("title", "calendar", "start", "end", "all_day", "status", "is_recurring")
    list_select_related = ("calendar",)
    list_filter = ("status", "all_day", "calendar")
    search_fields = ("title", "description", "location", "uid", "calendar__name")
    autocomplete_fields = ("calendar", "creator", "parent", "category", "resource", "location_resource", "decided_by")
    readonly_fields = ("uid", "href", "raw_ical", "sequence", "created_at", "updated_at")
    date_hierarchy = "start"
    ordering = ("-start",)
    inlines = (EventParticipantInline, EventCommentInline)
    fieldsets = (
        (None, {"fields": ("title", "calendar", "creator", "description", "category")}),
        (_("When"), {"fields": ("start", "end", "all_day", "timezone")}),
        (
            _("Recurrence"),
            {
                "classes": ("collapse",),
                "fields": ("rrule", "exdates", "rdates", "show_recurrence_count", "parent", "recurrence_id"),
            },
        ),
        (_("Where"), {"fields": ("location", "location_resource", "resource")}),
        (_("Approval"), {"fields": ("status", "awaiting_approval", "decided_by", "decided_at", "decision_note")}),
        (_("CalDAV"), {"classes": ("collapse",), "fields": ("uid", "href", "sequence", "raw_ical")}),
        (_("Dates"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description=_("Recurring"))
    def is_recurring(self, obj: models.Event) -> bool:
        return bool(obj.rrule)


@admin.register(models.EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin[models.EventParticipant]):
    list_display = ("email", "event", "user", "status")
    list_select_related = ("event", "user")
    list_filter = ("status",)
    search_fields = ("email", "event__title", "user__email")
    autocomplete_fields = ("event", "user")
    readonly_fields = ("rsvp_token", "created_at", "updated_at")


@admin.register(models.EventComment)
class EventCommentAdmin(admin.ModelAdmin[models.EventComment]):
    list_display = ("short_body", "event", "author", "created_at")
    list_select_related = ("event", "author")
    search_fields = ("body", "event__title", "author__email")
    autocomplete_fields = ("event", "author")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description=_("Comment"))
    def short_body(self, obj: models.EventComment) -> str:
        return obj.body if len(obj.body) <= 60 else f"{obj.body[:57]}..."


@admin.register(models.EventActivity)
class EventActivityAdmin(admin.ModelAdmin[models.EventActivity]):
    list_display = ("action", "event", "actor", "created_at")
    list_select_related = ("event", "actor")
    list_filter = ("action",)
    search_fields = ("event__title", "actor__email")
    autocomplete_fields = ("event", "actor")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(models.EventReminder)
class EventReminderAdmin(admin.ModelAdmin[models.EventReminder]):
    list_display = ("event", "user", "minutes_before", "created_at")
    list_select_related = ("event", "user")
    search_fields = ("event__title", "user__email")
    autocomplete_fields = ("event", "user")
    readonly_fields = ("created_at",)


@admin.register(models.ReminderDelivery)
class ReminderDeliveryAdmin(admin.ModelAdmin[models.ReminderDelivery]):
    list_display = ("reminder", "occurrence_start", "delivered_at")
    list_select_related = ("reminder__event", "reminder__user")
    raw_id_fields = ("reminder",)
    readonly_fields = ("delivered_at",)
    date_hierarchy = "delivered_at"


@admin.register(models.DeletedEvent)
class DeletedEventAdmin(admin.ModelAdmin[models.DeletedEvent]):
    list_display = ("href", "calendar_id", "deleted_at")
    search_fields = ("href", "calendar_id")
    readonly_fields = ("deleted_at",)
    date_hierarchy = "deleted_at"


@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin[models.Notification]):
    list_display = ("title", "type", "user", "is_read", "created_at")
    list_select_related = ("user",)
    list_filter = ("type",)
    search_fields = ("title", "user__email")
    autocomplete_fields = ("user", "actor", "calendar", "event")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(boolean=True, description=_("Read"))
    def is_read(self, obj: models.Notification) -> bool:
        return obj.read_at is not None
