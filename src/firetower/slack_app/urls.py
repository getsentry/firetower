from django.urls import path

from firetower.slack_app.views import slack_events

urlpatterns = [
    path("events", slack_events),
]
