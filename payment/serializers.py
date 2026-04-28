from rest_framework import serializers
from .models import *

class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.FloatField(source='plan.price',read_only=True)
    
    class Meta:
        model = Payments
        fields = '__all__'

class CheckoutSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(required=True)

    def validate(self, attrs):
        plan_id = attrs.get('plan_id')
        
        try:         
            plan = Plan.objects.get(id=plan_id)
            return plan
        except Plan.DoesNotExist:
            raise serializers.ValidationError({"status":False,"log":"Plan not found"})
        
        
        
    
    