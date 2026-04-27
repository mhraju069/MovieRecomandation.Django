from rest_framework import serializers
from .models import *

class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.FloatField(source='plan.price',read_only=True)
    
    class Meta:
        model = Payments
        fields = '__all__'
