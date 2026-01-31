import uuid
from django.db import models
from apps.products.models import Product
from apps.business.models import Location
from apps.accounts.models import User


class Batch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='batches'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='batches'
    )
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True, db_index=True)
    manufacture_date = models.DateField(blank=True, null=True)
    quantity = models.IntegerField(default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sell_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'batches'
        verbose_name_plural = 'batches'
        ordering = ['expiry_date', 'created_at']
        indexes = [
            models.Index(fields=['product', 'expiry_date']),
            models.Index(fields=['product', 'quantity']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.batch_number or 'No Batch'}"

    @property
    def stock_value(self):
        return self.quantity * self.cost_price

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        from django.utils import timezone
        delta = self.expiry_date - timezone.now().date()
        return delta.days


class InventoryTransaction(models.Model):
    TYPE_CHOICES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('ADJUST', 'Adjustment'),
    ]

    REASON_CHOICES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('damage', 'Damage'),
        ('expired', 'Expired'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('sample', 'Sample'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='inventory_transactions',
        null=True
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=50, choices=REASON_CHOICES, blank=True, null=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    synced_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'inventory_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch', 'created_at']),
            models.Index(fields=['type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.type} - {self.quantity} - {self.batch.product.name}"

    def save(self, *args, **kwargs):
        # Update batch quantity
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            if self.type == 'IN':
                self.batch.quantity += self.quantity
            elif self.type == 'OUT':
                self.batch.quantity -= self.quantity
            else:  # ADJUST
                self.batch.quantity += self.quantity
            self.batch.save()


class Label(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='labels'
    )
    qr_code = models.CharField(max_length=255)
    printed_at = models.DateTimeField(auto_now_add=True)
    printed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        db_table = 'labels'
        ordering = ['-printed_at']

    def __str__(self):
        return f"Label for {self.batch}"
