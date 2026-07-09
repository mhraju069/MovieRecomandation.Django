from .models import User, Blocks
from rest_framework import serializers
from .helper import verify_otp,send_otp


class SignUpSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['email', 'name', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            name=validated_data.get('name', ''),
            password=validated_data['password']
        )
        return user




class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = User.objects.filter(email=email).first()
            if user:
                if not user.check_password(password):
                     raise serializers.ValidationError("Invalid credentials")
                if not user.is_active:
                    raise serializers.ValidationError("User is not active")
                if user.block:
                    raise serializers.ValidationError("User is blocked")
                attrs['user'] = user
                return attrs
            else:
                raise serializers.ValidationError("User not found")
        raise serializers.ValidationError("Email and password are required")




class UserProfileSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = User
        exclude = ['last_login', 'block', 'role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'created_at']
        read_only_fields = ['id', 'email']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def update(self, instance, validated_data):
        # Update name, image, bio, and notify if provided
        instance.name = validated_data.get('name', instance.name)
        instance.image = validated_data.get('image', instance.image)
        instance.bio = validated_data.get('bio', instance.bio)
        instance.notify = validated_data.get('notify', instance.notify)

        # Handle password update
        old_password = validated_data.get('old_password')
        new_password = validated_data.get('password')
        username = validated_data.get('username')

        if username:
            # Check if username exists and is not the current user
            existing_username = User.objects.filter(username=username).exclude(id=instance.id).first()
            if existing_username:
                raise serializers.ValidationError({"error": "Username already exists."})
            instance.username = username

        if new_password:
            if not old_password:
                raise serializers.ValidationError({"error": "Current password is required to set a new password."})
            
            if not instance.check_password(old_password):
                raise serializers.ValidationError({"error": "Old password does not match."})
            
            instance.set_password(new_password)

        instance.save()
        return instance




class GetOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    task = serializers.CharField(max_length=100,required=False,allow_blank=True,allow_null=True)

    def validate(self, attrs):
        email = attrs.get('email')
        task = attrs.get('task')
        
        res = send_otp(email, task)

        return res
    



class VerifyOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        email = attrs.get('email')
        otp_code = attrs.get('otp')

        res = verify_otp(email, otp_code)
        return res




class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = self.context['request'].user.email
        new_password = attrs.get('new_password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"status":False,"log":"User not found"})

        user.set_password(new_password)
        user.save()
        return {"status": True, "log": "Password reset successfully"}


class BlocksSerializer(serializers.ModelSerializer):
    blocked_user_details = UserProfileSerializer(source='blocked', read_only=True)

    class Meta:
        model = Blocks
        fields = ['id', 'blocked', 'blocked_user_details', 'created_at']
        read_only_fields = ['id', 'created_at']





