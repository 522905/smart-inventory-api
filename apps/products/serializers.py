from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'business_id', 'name', 'parent_id']
        read_only_fields = ['id']


class ProductSerializer(serializers.ModelSerializer):
    total_stock = serializers.IntegerField(read_only=True)
    batch_count = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'business_id', 'category_id', 'category_name',
            'name', 'sku', 'barcode', 'unit', 'min_stock',
            'is_active', 'created_at', 'total_stock', 'batch_count', 'is_low_stock'
        ]
        read_only_fields = ['id', 'created_at', 'total_stock', 'batch_count']


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'category_id', 'name', 'sku', 'barcode',
            'unit', 'min_stock', 'is_active'
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['business'] = self.context['request'].user.business
        return super().create(validated_data)
