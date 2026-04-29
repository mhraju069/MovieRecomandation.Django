from rest_framework import serializers
from .models import *

class GetProvidersSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()
    provider_name = serializers.CharField()
    logo_path = serializers.CharField()



class GetGenresSerializer(serializers.Serializer):
    genre_id = serializers.IntegerField()
    genre_name = serializers.CharField()
    


class PrefrencesSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    platform = serializers.JSONField(required=True)
    genre = serializers.JSONField(required=True)

    class Meta:
        model = UserPrefrences
        fields = ["user","platform","genre"]

    def validate(self, attrs):
        platform = attrs.get("platform")
        genre = attrs.get("genre")

        if not platform or not genre:
            raise serializers.ValidationError("Platform and Genre are required")
        
        if not isinstance(platform, list) or not isinstance(genre, list):
            raise serializers.ValidationError("Platform and Genre must be lists")

        if not platform and not genre:
            raise serializers.ValidationError("Platform or Genre must be present")

        return attrs

    