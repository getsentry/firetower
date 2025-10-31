from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import ExternalProfile, UserProfile
from .services import sync_user_profile_from_slack


# Customize User string representation
def user_str(self):
    return self.email or self.username


User.__str__ = user_str


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


class ExternalProfileInline(admin.TabularInline):
    model = ExternalProfile
    extra = 1


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, ExternalProfileInline)
    list_display = ["username", "email", "first_name", "last_name", "is_staff"]
    search_fields = ["username", "email", "first_name", "last_name"]
    actions = ["sync_with_slack"]

    @admin.action(description="Sync selected users with Slack")
    def sync_with_slack(self, request, queryset):
        """Sync selected users' profiles (name, avatar) from Slack."""
        updated_count = 0
        skipped_count = 0

        for user in queryset:
            if sync_user_profile_from_slack(user):
                updated_count += 1
            else:
                skipped_count += 1

        total = queryset.count()
        self.message_user(
            request,
            f"Synced {total} user(s): {updated_count} updated, {skipped_count} skipped/unchanged.",
        )


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "avatar_url"]
    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]


@admin.register(ExternalProfile)
class ExternalProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "type", "external_id", "created_at"]
    list_filter = ["type"]
    search_fields = ["user__username", "external_id"]
