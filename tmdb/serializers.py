from rest_framework import serializers

class GetProvidersSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()
    provider_name = serializers.CharField()
    logo_path = serializers.CharField()

    
