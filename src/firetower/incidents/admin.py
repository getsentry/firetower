from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
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

    filter_horizontal = [
        "participants",
        "affected_service_tags",
        "affected_region_tags",
        "root_cause_tags",
        "impact_type_tags",
    ]

    actions = ["sync_participants_from_slack", "clear_milestones"]

    inlines = [ExternalLinkInline]

    fieldsets = (
        (
            "Incident Information",
            {"fields": ("title", "description", "impact_summary")},
        ),
        ("Status", {"fields": ("status", "severity", "service_tier", "is_private")}),
        ("People", {"fields": ("captain", "reporter", "participants")}),
        (
            "Tags",
            {
                "fields": (
                    "affected_service_tags",
                    "affected_region_tags",
                    "root_cause_tags",
                    "impact_type_tags",
                )
            },
        ),
        (
            "Milestones",
            {
                "fields": (
                    "time_started",
                    "time_detected",
                    "time_analyzed",
                    "time_mitigated",
                    "time_recovered",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def incident_number_display(self, obj: Incident) -> str:
        return obj.incident_number

    incident_number_display.short_description = "Incident #"
    incident_number_display.admin_order_field = "id"

    @admin.action(description="Sync participants from Slack")
    def sync_participants_from_slack(
        self, request: HttpRequest, queryset: QuerySet[Incident]
    ) -> None:
        success_count = 0
        skipped_count = 0
        error_count = 0

        for incident in queryset:
            try:
                stats = sync_incident_participants_from_slack(incident, force=True)
                if stats.errors:
                    error_count += 1
                elif stats.skipped:
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

    @admin.action(description="Clear all milestones")
    def clear_milestones(
        self, request: HttpRequest, queryset: QuerySet[Incident]
    ) -> None:
        count = queryset.update(
            time_started=None,
            time_detected=None,
            time_analyzed=None,
            time_mitigated=None,
            time_recovered=None,
        )
        self.message_user(request, f"Cleared milestones for {count} incident(s)")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "approved", "created_at"]
    list_filter = ["type", "approved"]
    search_fields = ["name"]
    actions = ["approve_tags"]

    @admin.action(description="Approve selected tags")
    def approve_tags(self, request: HttpRequest, queryset: QuerySet[Tag]) -> None:
        count = queryset.update(approved=True)
        self.message_user(request, f"Approved {count} tag(s).")


@admin.register(ExternalLink)
class ExternalLinkAdmin(admin.ModelAdmin):
    list_display = ["incident", "type", "url"]
    list_filter = ["type"]
    search_fields = ["incident__id", "url"]
