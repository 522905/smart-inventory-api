from rest_framework import serializers
from django.db import transaction
from .models import Batch, InventoryTransaction, Label


class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_barcode = serializers.CharField(source='product.barcode', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    stock_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model = Batch
        fields = [
            'id', 'product_id', 'product_name', 'product_barcode',
            'location_id', 'location_name', 'batch_number',
            'expiry_date', 'manufacture_date', 'quantity',
            'cost_price', 'sell_price', 'created_at',
            'stock_value', 'is_expired', 'days_until_expiry'
        ]
        read_only_fields = ['id', 'created_at']


class BatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = [
            'product_id', 'location_id', 'batch_number',
            'expiry_date', 'manufacture_date', 'quantity',
            'cost_price', 'sell_price'
        ]

    def create(self, validated_data):
        batch = super().create(validated_data)

        # Create initial transaction
        InventoryTransaction.objects.create(
            batch=batch,
            user=self.context['request'].user,
            type='IN',
            quantity=batch.quantity,
            reason='purchase',
            notes='Initial stock'
        )

        return batch


class TransactionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    product_name = serializers.CharField(source='batch.product.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)

    class Meta:
        model = InventoryTransaction
        fields = [
            'id', 'batch_id', 'user_id', 'user_name',
            'type', 'quantity', 'reason', 'reference', 'notes',
            'created_at', 'synced_at', 'product_name', 'batch_number'
        ]
        read_only_fields = ['id', 'created_at', 'user_id']


class InwardSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        batch = Batch.objects.get(id=validated_data['batch_id'])

        transaction = InventoryTransaction.objects.create(
            batch=batch,
            user=self.context['request'].user,
            type='IN',
            quantity=validated_data['quantity'],
            reason='purchase',
            reference=validated_data.get('reference'),
            notes=validated_data.get('notes'),
        )

        return transaction


class OutwardSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=InventoryTransaction.REASON_CHOICES)
    reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        batch = Batch.objects.get(id=attrs['batch_id'])
        if batch.quantity < attrs['quantity']:
            raise serializers.ValidationError({
                'quantity': f'Insufficient stock. Available: {batch.quantity}'
            })
        return attrs

    def create(self, validated_data):
        batch = Batch.objects.get(id=validated_data['batch_id'])

        transaction = InventoryTransaction.objects.create(
            batch=batch,
            user=self.context['request'].user,
            type='OUT',
            quantity=validated_data['quantity'],
            reason=validated_data['reason'],
            reference=validated_data.get('reference'),
            notes=validated_data.get('notes'),
        )

        return transaction


class AdjustmentSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    quantity = serializers.IntegerField()  # Can be positive or negative
    reason = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        batch = Batch.objects.get(id=attrs['batch_id'])
        new_quantity = batch.quantity + attrs['quantity']
        if new_quantity < 0:
            raise serializers.ValidationError({
                'quantity': 'Adjustment would result in negative stock'
            })
        return attrs

    def create(self, validated_data):
        batch = Batch.objects.get(id=validated_data['batch_id'])

        transaction = InventoryTransaction.objects.create(
            batch=batch,
            user=self.context['request'].user,
            type='ADJUST',
            quantity=validated_data['quantity'],
            reason='adjustment',
            notes=f"{validated_data['reason']}: {validated_data.get('notes', '')}",
        )

        return transaction


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'batch_id', 'qr_code', 'printed_at', 'printed_by']
        read_only_fields = ['id', 'printed_at']

    def create(self, validated_data):
        validated_data['printed_by'] = self.context['request'].user
        return super().create(validated_data)
