from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, ExternalProfile


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


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "is_admin", "avatar_url"]
    list_filter = ["is_admin"]
    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]


@admin.register(ExternalProfile)
class ExternalProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "profile_type", "external_id", "created_at"]
    list_filter = ["profile_type"]
    search_fields = ["user__username", "external_id"]
