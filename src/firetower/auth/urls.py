from django.urls import path

from .views import current_user, user_list

urlpatterns = [
    path("users/", user_list, name="user-list"),
    path("ui/users/me/", current_user, name="current-user"),
]
