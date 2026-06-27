from django.shortcuts import render
from rest_framework import generics, permissions, response, status
from rest_framework.views import APIView
from .models import *
from .serializers import *

# Create your views here.


class NotificationViewSet(generics.ListAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-created_at')




class FCMDeviceView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FCMDeviceSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not serializer.validated_data.get('registration_id'):
            return response.Response({"error": "registration_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Update or create the device token
        device, created = FCMDevice.objects.update_or_create(
            registration_id=serializer.validated_data['registration_id'],
            defaults={
                'user': request.user,
                'device_id': request.data.get('device_id'),
                'active': True
            }
        )
        
        serializer = FCMDeviceSerializer(device)
        return response.Response(serializer.data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)
    




class UpdateNotificationStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.filter(id=notification_id, user=request.user).first()
            if not notification:
                return response.Response({"status": False, "log": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

            notification.is_read = True
            notification.save()
            return response.Response({"status": True, "log": "Notification marked as read"}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in UpdateNotificationStatusView:", e)
            return response.Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import random
from django.contrib.auth import get_user_model
from .utils import send_fcm_to_user

User = get_user_model()

from drf_yasg.utils import swagger_auto_schema

class SendCustomNotificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=SendCustomNotificationSerializer,
        responses={200: "Success Response"},
        operation_summary="Send custom notification",
        operation_description="Send custom notification to user",
    )
    def post(self, request):
        serializer = SendCustomNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data.get('user_id')
        title = serializer.validated_data['title']
        message = serializer.validated_data['message']
        movie_id = serializer.validated_data.get('movie_id')
        media_type = serializer.validated_data.get('type', 'movie')

        if not movie_id:
            movie_id = random.randint(100000, 999999)

        if user_id:
            try:
                users = [User.objects.get(id=user_id)]
            except User.DoesNotExist:
                return response.Response({"status": False, "log": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            users = User.objects.filter(is_active=True, notify=True)

        success_count = 0
        fcm_sent_count = 0

        for user in users:
            try:
                # Check for unique_together collision
                if Notification.objects.filter(user=user, movie_id=movie_id, type=media_type).exists():
                    notification = Notification.objects.get(user=user, movie_id=movie_id, type=media_type)
                    notification.title = title
                    notification.message = message
                    notification.save()
                else:
                    Notification.objects.create(
                        user=user,
                        movie_id=movie_id,
                        type=media_type,
                        title=title,
                        message=message,
                    )
                success_count += 1

                # Send FCM push
                fcm_resp = send_fcm_to_user(
                    user=user,
                    title=title,
                    body=message,
                    data={
                        'movie_id': str(movie_id),
                        'type': media_type
                    }
                )
                if fcm_resp:
                    fcm_sent_count += 1
            except Exception as e:
                print(f"Error sending notification to user {user.id}: {e}")

        return response.Response({
            "status": True,
            "log": f"Notification processed for {success_count} user(s). FCM push notifications sent to {fcm_sent_count} user(s).",
            "details": {
                "total_targeted_users": len(users),
                "db_notifications_created_or_updated": success_count,
                "fcm_pushes_sent": fcm_sent_count
            }
        }, status=status.HTTP_200_OK)