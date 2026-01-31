import uuid
from django.db import models
from apps.business.models import Business


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'
        ordering = ['name']
        unique_together = ['business', 'name', 'parent']

    def __str__(self):
        return self.name


class Product(models.Model):
    UNIT_CHOICES = [
        ('pcs', 'Pieces'),
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('ltr', 'Liters'),
        ('ml', 'Milliliters'),
        ('box', 'Box'),
        ('pack', 'Pack'),
        ('strip', 'Strip'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='products'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='products',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True, null=True)
    barcode = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES, default='pcs')
    min_stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['business', 'barcode']),
            models.Index(fields=['business', 'name']),
        ]

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        """Calculate total stock across all batches."""
        return self.batches.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    @property
    def batch_count(self):
        """Count of active batches."""
        return self.batches.filter(quantity__gt=0).count()

    @property
    def is_low_stock(self):
        """Check if stock is below minimum."""
        return self.total_stock <= self.min_stock
