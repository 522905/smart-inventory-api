from rest_framework import serializers
from django.utils import timezone
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
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)

    # New computed fields
    stock_value = serializers.SerializerMethodField()
    nearest_expiry = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'business_id', 'category_id', 'category_name',
            'name', 'sku', 'barcode', 'unit', 'min_stock',
            'is_active', 'created_at', 'total_stock', 'batch_count', 'is_low_stock',
            'stock_value', 'nearest_expiry', 'stock_status'
        ]
        read_only_fields = ['id', 'created_at', 'total_stock', 'batch_count']

    def get_stock_value(self, obj):
        """Calculate total stock value (quantity × cost_price) across all batches."""
        from apps.inventory.models import Batch
        batches = Batch.objects.filter(product=obj, quantity__gt=0)
        total = sum(
            (b.quantity or 0) * float(b.cost_price or 0)
            for b in batches
        )
        return round(total, 2)

    def get_nearest_expiry(self, obj):
        """Get the closest expiry date from all active batches."""
        from apps.inventory.models import Batch
        today = timezone.now().date()
        batch = Batch.objects.filter(
            product=obj,
            quantity__gt=0,
            expiry_date__gte=today
        ).order_by('expiry_date').first()

        if batch and batch.expiry_date:
            return batch.expiry_date.isoformat()
        return None

    def get_stock_status(self, obj):
        """
        Determine stock status:
        - 'out' - No stock (total_stock = 0)
        - 'critical' - Stock at or below 25% of min_stock
        - 'low' - Stock at or below min_stock
        - 'healthy' - Stock above min_stock
        """
        total = obj.total_stock
        min_stock = obj.min_stock or 0

        if total == 0:
            return 'out'
        if min_stock > 0:
            if total <= min_stock * 0.25:
                return 'critical'
            if total <= min_stock:
                return 'low'
        return 'healthy'


class ProductCreateSerializer(serializers.ModelSerializer):
    business_id = serializers.UUIDField(source='business.id', read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'business_id', 'category_id', 'name', 'sku', 'barcode',
            'unit', 'min_stock', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'business_id', 'created_at']

    def create(self, validated_data):
        validated_data['business'] = self.context['request'].user.business
        return super().create(validated_data)
