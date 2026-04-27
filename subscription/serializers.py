from rest_framework import serializers
from .models import *

class PlanSerializers(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id','name','data', 'duration', 'price']
        
class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializers(read_only=True)
    
    class Meta:
        model = Subscriptions
        fields = ['plan', 'start', 'end']
        read_only_fields = ['user', 'start', 'end']