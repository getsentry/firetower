from django.contrib import admin

from .models import ExternalLink, Incident, Tag


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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ["captain", "reporter"]:
            kwargs["label_from_instance"] = lambda obj: obj.email or obj.username
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "participants":
            kwargs["label_from_instance"] = lambda obj: obj.email or obj.username
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def incident_number_display(self, obj):
        return obj.incident_number

    incident_number_display.short_description = "Incident #"
    incident_number_display.admin_order_field = "id"


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
