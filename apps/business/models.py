import uuid
from django.db import models


class Business(models.Model):
    TYPE_CHOICES = [
        ('pharmacy', 'Pharmacy'),
        ('retail', 'Retail Store'),
        ('warehouse', 'Warehouse'),
        ('distributor', 'Distributor'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='retail')
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'businesses'
        verbose_name_plural = 'businesses'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='locations'
    )
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'locations'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.business.name} - {self.name}"

    def save(self, *args, **kwargs):
        # Ensure only one default location per business
        if self.is_default:
            Location.objects.filter(
                business=self.business,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
