from rest_framework import serializers
from .models import *


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = '__all__'



class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class SendCustomNotificationSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255)
    message = serializers.CharField(required=True)
    movie_id = serializers.IntegerField(required=False, allow_null=True)
    type = serializers.ChoiceField(choices=[('movie', 'Movie'), ('tv', 'TV')], default='movie')