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



class ReportsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reports
        fields = [
            'id', 
            'type', 
            'user',
            'reported_user', 
            'reported_post', 
            'reported_review', 
            'reported_feed_post_comment', 
            'reported_rating_comment', 
            'reason',
            'is_resolved', 
            'remark', 
            'reported_at',
            'resolved_at'
        ]
        read_only_fields = ['id', 'user', 'is_resolved', 'remark', 'reported_at', 'resolved_at']

    def validate(self, attrs):
        report_type = attrs.get('type')
        
        type_field_map = {
            'USER': 'reported_user',
            'POST': 'reported_post',
            'REVIEW': 'reported_review',
            'POST_COMMENT': 'reported_feed_post_comment',
            'RATING_COMMENT': 'reported_rating_comment',
        }
        
        target_field = type_field_map.get(report_type)
        if not target_field:
            raise serializers.ValidationError({"type": "Invalid report type."})
            
        if not attrs.get(target_field):
            raise serializers.ValidationError({target_field: f"This field is required when report type is {report_type}."})
            
        for key, field_name in type_field_map.items():
            if field_name != target_field and attrs.get(field_name):
                attrs[field_name] = None
                
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)



