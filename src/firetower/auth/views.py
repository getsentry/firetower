from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import UserSerializer


@api_view(["GET"])
def current_user(request):
    """
    Return the current authenticated user's profile.

    Authentication enforced via DEFAULT_PERMISSION_CLASSES in settings.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)
