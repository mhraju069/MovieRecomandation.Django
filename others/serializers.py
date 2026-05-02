from rest_framework import serializers
from .models import *


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = '__all__'



class SupportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Support
        fields = '__all__'



class PrivacyPolicyContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyPolicyContent
        exclude = ('policy',)



class PrivacyPolicySerializer(serializers.ModelSerializer):
    content_blocks = PrivacyPolicyContentSerializer(source='contents', many=True, read_only=True)
    
    class Meta:
        model = PrivacyPolicy
        fields = ['updated_at', 'content_blocks']
        read_only_fields = ['updated_at']



class TermsAndConditionsContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndConditionsContent
        exclude = ('terms',)



class TermsAndConditionsSerializer(serializers.ModelSerializer):
    content_blocks = TermsAndConditionsContentSerializer(source='contents', many=True, read_only=True)
    
    class Meta:
        model = TermsAndConditions
        fields = ['effective_date','updated_at', 'content_blocks']
        read_only_fields = ['effective_date','updated_at']
