from django.contrib.auth.models import User
from django.db.models import Q, QuerySet, Value
from django.db.models.functions import Concat
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .serializers import UserListSerializer, UserSerializer


@api_view(["GET"])
def current_user(request: Request) -> Response:
    """
    Return the current authenticated user's profile.

    Authentication enforced via DEFAULT_PERMISSION_CLASSES in settings.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class UserListView(generics.ListAPIView):
    serializer_class = UserListSerializer

    def get_queryset(self) -> QuerySet[User]:
        queryset = (
            User.objects.select_related("userprofile")
            .exclude(email="")
            .order_by("email")
        )
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.annotate(
                full_name=Concat("first_name", Value(" "), "last_name")
            ).filter(Q(full_name__icontains=search) | Q(email__icontains=search))
        return queryset


user_list = UserListView.as_view()
