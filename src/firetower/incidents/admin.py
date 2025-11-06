from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.db.models import ForeignKey, ManyToManyField
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.http import HttpRequest

from .models import ExternalLink, Incident, Tag
from .services import sync_incident_participants_from_slack


class ExternalLinkInline(admin.TabularInline):
    model = ExternalLink
    extra = 1


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = [
        "incident_number_display",
        "title",
        "status",
        "severity",
        "captain",
        "is_private",
        "created_at",
    ]
    list_filter = ["status", "severity", "is_private", "created_at"]
    search_fields = ["title", "description", "id"]
    readonly_fields = ["created_at", "updated_at"]

    filter_horizontal = ["participants", "affected_area_tags", "root_cause_tags"]

    actions = ["sync_participants_from_slack"]

    inlines = [ExternalLinkInline]

    fieldsets = (
        (
            "Incident Information",
            {"fields": ("title", "description", "impact")},
        ),
        ("Status", {"fields": ("status", "severity", "is_private")}),
        ("People", {"fields": ("captain", "reporter", "participants")}),
        ("Tags", {"fields": ("affected_area_tags", "root_cause_tags")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def formfield_for_foreignkey(
        self, db_field: ForeignKey[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> ModelChoiceField | None:
        if db_field.name in ["captain", "reporter"]:
            kwargs["label_from_instance"] = lambda obj: obj.email or obj.username
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(
        self, db_field: ManyToManyField[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> ModelMultipleChoiceField | None:
        if db_field.name == "participants":
            kwargs["label_from_instance"] = lambda obj: obj.email or obj.username
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def incident_number_display(self, obj: Incident) -> str:
        return obj.incident_number

    incident_number_display.short_description = "Incident #"
    incident_number_display.admin_order_field = "id"

    @admin.action(description="Sync participants from Slack")
    def sync_participants_from_slack(self, request, queryset):
        success_count = 0
        skipped_count = 0
        error_count = 0

        for incident in queryset:
            try:
                stats = sync_incident_participants_from_slack(incident, force=True)
                if stats["errors"]:
                    error_count += 1
                elif stats["skipped"]:
                    skipped_count += 1
                else:
                    success_count += 1
            except Exception:
                error_count += 1

        message_parts = []
        if success_count:
            message_parts.append(f"{success_count} synced successfully")
        if skipped_count:
            message_parts.append(f"{skipped_count} skipped")
        if error_count:
            message_parts.append(f"{error_count} failed")

        self.message_user(request, f"Participant sync: {', '.join(message_parts)}")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "created_at"]
    list_filter = ["type"]
    search_fields = ["name"]


@admin.register(ExternalLink)
class ExternalLinkAdmin(admin.ModelAdmin):
    list_display = ["incident", "type", "url"]
    list_filter = ["type"]
    search_fields = ["incident__id", "url"]
