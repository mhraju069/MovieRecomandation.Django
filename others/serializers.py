from rest_framework import serializers
from .models import FAQ, Support


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = '__all__'



class SupportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Support
        fields = '__all__'