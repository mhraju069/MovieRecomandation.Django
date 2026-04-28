from rest_framework import generics, status,permissions
from rest_framework.response import Response
from django.conf import settings
from django.core.cache import cache
import requests
from .serializers import *

# Create your views here.


class GetProvidersView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GetProvidersSerializer

    def get(self, request):
        cached_data = cache.get("tmdb_providers")
        if cached_data:
            print("Using cached data")
            return Response({"status": True, "log": self.get_serializer(cached_data, many=True).data}, status=status.HTTP_200_OK)   
        
        try:
            print("Using fresh data")
            access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', None)
            if not access_token:
                return Response({"status": False,"log": "TMDB access token not configured."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            headers = {
                "Authorization": f"Bearer {access_token}"
            }

            res = requests.get(
                "https://api.themoviedb.org/3/watch/providers/tv",
                headers=headers
            )
            res.raise_for_status()

            data = res.json().get("results", [])

            response = [
                {
                    "provider_id": i.get("provider_id"),
                    "provider_name": i.get("provider_name"),
                    "logo_path": f"https://image.tmdb.org/t/p/original{i.get('logo_path')}",
                }
                for i in data[:20]
            ]

            cache.set("tmdb_providers", response, timeout=86400)

            return Response({"status": True, "log": self.get_serializer(response, many=True).data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)

