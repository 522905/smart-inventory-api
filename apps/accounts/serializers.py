from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from apps.business.models import Business
from apps.business.serializers import BusinessSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'business_id', 'email', 'name', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class RegisterSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=255)
    business_type = serializers.ChoiceField(choices=[
        ('pharmacy', 'Pharmacy'),
        ('retail', 'Retail Store'),
        ('warehouse', 'Warehouse'),
        ('distributor', 'Distributor'),
        ('other', 'Other'),
    ])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    name = serializers.CharField(max_length=255)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered')
        return value

    def create(self, validated_data):
        # Create business
        business = Business.objects.create(
            name=validated_data['business_name'],
            type=validated_data['business_type'],
        )

        # Create user as owner
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data['name'],
            business=business,
            role='owner',
        )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError('Invalid email or password')

        if not user.is_active:
            raise serializers.ValidationError('Account is disabled')

        attrs['user'] = user
        return attrs


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()
    business = BusinessSerializer(required=False)

    @classmethod
    def get_tokens_for_user(cls, user):
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'business': BusinessSerializer(user.business).data if user.business else None,
        }
