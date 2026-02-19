from django.http import HttpResponse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from slack_bolt.adapter.django import SlackRequestHandler

from firetower.slack_app.authentication import SlackSigningSecretAuthentication
from firetower.slack_app.bolt import bolt_app

handler = SlackRequestHandler(app=bolt_app)


@api_view(["POST"])
@authentication_classes([SlackSigningSecretAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([FormParser, JSONParser])
def slack_events(request: Request) -> HttpResponse:
    return handler.handle(request._request)
