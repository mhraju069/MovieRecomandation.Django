from django.shortcuts import render
from rest_framework import generics, permissions,response, status
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
    




class UpdateNotificationStatusView(generics.GenericAPIView):
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