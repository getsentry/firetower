from django.urls import path

from .views import current_user

urlpatterns = [
    path("ui/users/me/", current_user, name="current-user"),
]
