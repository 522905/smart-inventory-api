from rest_framework import serializers
from .models import Business, Location


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'type', 'phone', 'address', 'created_at']
        read_only_fields = ['id', 'created_at']


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'business_id', 'name', 'address', 'is_default']
        read_only_fields = ['id']
