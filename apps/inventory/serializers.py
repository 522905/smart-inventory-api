from rest_framework import serializers
from django.db import transaction
from .models import Batch, InventoryTransaction, Label


class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, allow_null=True)
    product_barcode = serializers.CharField(source='product.barcode', read_only=True, allow_null=True)
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    stock_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True, allow_null=True)

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
    # Handle IDs as strings to avoid UUID validation issues
    product_id = serializers.UUIDField()
    location_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Batch
        fields = [
            'id', 'product_id', 'location_id', 'batch_number',
            'expiry_date', 'manufacture_date', 'quantity',
            'cost_price', 'sell_price', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        from apps.business.models import Location
        from apps.products.models import Product

        user = self.context['request'].user

        # Check if user has a business
        if not user.business:
            raise serializers.ValidationError({
                'detail': 'User is not associated with any business'
            })

        # Handle product_id
        product_id = validated_data.pop('product_id', None)
        if not product_id:
            raise serializers.ValidationError({
                'product_id': 'Product ID is required'
            })
        try:
            product = Product.objects.get(id=product_id)
            validated_data['product'] = product
        except Product.DoesNotExist:
            raise serializers.ValidationError({
                'product_id': 'Product not found'
            })

        # Get location_id and handle empty string
        location_id = validated_data.pop('location_id', None)
        if not location_id or location_id == '':
            # Use default location for the user's business
            default_location = Location.objects.filter(
                business=user.business,
                is_default=True
            ).first()

            if not default_location:
                # Create a default location if none exists
                default_location = Location.objects.create(
                    business=user.business,
                    name='Main Warehouse',
                    is_default=True
                )

            validated_data['location'] = default_location
        else:
            # Get location by ID
            try:
                location = Location.objects.get(id=location_id)
                validated_data['location'] = location
            except Location.DoesNotExist:
                raise serializers.ValidationError({
                    'location_id': 'Location not found'
                })

        # Store initial quantity
        initial_quantity = validated_data.pop('quantity', 0)

        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Create batch with initial quantity directly
            validated_data['quantity'] = initial_quantity
            batch = super().create(validated_data)

            # Create initial transaction for record keeping (skip auto quantity update)
            txn = InventoryTransaction(
                batch=batch,
                user=user,
                type='IN',
                quantity=initial_quantity,
                reason='purchase',
                notes='Initial stock'
            )
            txn.save(skip_quantity_update=True)

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


class QuickInSerializer(serializers.Serializer):
    """
    Quick Stock In: Create batch + record inward in one call.
    Simplified workflow for receiving stock.
    """
    product_id = serializers.UUIDField()
    batch_number = serializers.CharField(max_length=100)
    quantity = serializers.IntegerField(min_value=1)
    cost_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    sell_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    manufacture_date = serializers.DateField(required=False, allow_null=True)
    location_id = serializers.UUIDField(required=False, allow_null=True)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_product_id(self, value):
        from apps.products.models import Product
        user = self.context['request'].user
        try:
            product = Product.objects.get(id=value, business=user.business)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError('Product not found')

    def create(self, validated_data):
        from apps.business.models import Location
        from apps.products.models import Product

        user = self.context['request'].user

        # Get product
        product = Product.objects.get(id=validated_data['product_id'])

        # Get or create default location
        location_id = validated_data.get('location_id')
        if location_id:
            try:
                location = Location.objects.get(id=location_id, business=user.business)
            except Location.DoesNotExist:
                raise serializers.ValidationError({'location_id': 'Location not found'})
        else:
            location = Location.objects.filter(business=user.business, is_default=True).first()
            if not location:
                location = Location.objects.create(
                    business=user.business,
                    name='Main Warehouse',
                    is_default=True
                )

        # Create batch with initial quantity
        with transaction.atomic():
            batch = Batch.objects.create(
                product=product,
                location=location,
                batch_number=validated_data['batch_number'],
                quantity=validated_data['quantity'],
                cost_price=validated_data['cost_price'],
                sell_price=validated_data.get('sell_price'),
                expiry_date=validated_data.get('expiry_date'),
                manufacture_date=validated_data.get('manufacture_date'),
            )

            # Create transaction record (skip auto quantity update since we set it directly)
            txn = InventoryTransaction(
                batch=batch,
                user=user,
                type='IN',
                quantity=validated_data['quantity'],
                reason='purchase',
                reference=validated_data.get('reference', ''),
                notes=validated_data.get('notes', 'Quick stock in'),
            )
            txn.save(skip_quantity_update=True)

        return {'batch': batch, 'transaction': txn}


class QuickOutSerializer(serializers.Serializer):
    """
    Quick Stock Out: Auto-select batches using FEFO and deduct stock.
    Simplified workflow for issuing stock.
    """
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=InventoryTransaction.REASON_CHOICES, default='sale')
    reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        from apps.products.models import Product
        user = self.context['request'].user

        # Validate product exists and belongs to user's business
        try:
            product = Product.objects.get(id=attrs['product_id'], business=user.business)
        except Product.DoesNotExist:
            raise serializers.ValidationError({'product_id': 'Product not found'})

        # Check total available stock
        total_stock = product.total_stock
        if total_stock < attrs['quantity']:
            raise serializers.ValidationError({
                'quantity': f'Insufficient stock. Available: {total_stock}'
            })

        attrs['product'] = product
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']
        quantity_to_deduct = validated_data['quantity']

        # Get batches ordered by expiry date (FEFO - First Expiry First Out)
        # Batches with null expiry_date come last
        batches = Batch.objects.filter(
            product=product,
            quantity__gt=0
        ).order_by('expiry_date')

        transactions = []
        remaining = quantity_to_deduct

        with transaction.atomic():
            for batch in batches:
                if remaining <= 0:
                    break

                # Deduct from this batch
                deduct_qty = min(batch.quantity, remaining)

                txn = InventoryTransaction.objects.create(
                    batch=batch,
                    user=user,
                    type='OUT',
                    quantity=deduct_qty,
                    reason=validated_data['reason'],
                    reference=validated_data.get('reference', ''),
                    notes=validated_data.get('notes', 'Quick stock out'),
                )
                transactions.append(txn)
                remaining -= deduct_qty

        return {
            'product': product,
            'total_deducted': quantity_to_deduct,
            'transactions': transactions,
            'batches_affected': len(transactions),
        }
