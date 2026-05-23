
from .views import *
from django.urls import path

urlpatterns = [
    path('notifications/', NotificationViewSet.as_view(), name='notifications'),
    path('register-device/', FCMDeviceView.as_view(), name='register_device'),
    path('notifications/read/<uuid:notification_id>/', UpdateNotificationStatusView.as_view(), name='notification_read'),
]