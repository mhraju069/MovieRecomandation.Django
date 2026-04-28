import requests,json
from django.conf import settings
from django.core.cache import cache
from .models import *
from .helper import *
from .serializers import *
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import generics, status,permissions
from rest_framework_simplejwt.tokens import RefreshToken

# Create your views here.

class SignUpView(generics.CreateAPIView):
    serializer_class = SignUpSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "status": True,
            "log": UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)



    
class SignInView(generics.CreateAPIView):
    serializer_class = SignInSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            "status": True,
            "log": UserProfileSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)




class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_object(self):
        return User.objects.filter(email=self.request.user.email).first()




class GetOtpView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GetOtpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = serializer.validated_data
        if res.get('status'):
            return Response(res, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)




class OtpVerifyView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = VerifyOtpSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = serializer.validated_data
        if res.get('status'):
            try:
                user = User.objects.get(email=request.data.get('email'))
            except User.DoesNotExist:
                return Response({"status": False,"log": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            refresh = RefreshToken.for_user(user)
            return Response({
                "log": UserProfileSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)
        



class ResetPasswordView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        res = serializer.validated_data
        if res.get('status'):
            return Response(res, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)




class GetProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = UserProfileSerializer(request.user,context={"request": request}).data
        return Response({"status": True, "log": user}, status=200)




class GetProvidersView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GetPlatformSerializer

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

