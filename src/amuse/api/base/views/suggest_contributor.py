from releases.utils import get_contributors_from_history
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class SuggestContributor(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        contributors = get_contributors_from_history(user=user)
        return Response(data={'contributors': contributors})
