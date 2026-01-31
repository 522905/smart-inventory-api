from django.contrib import admin
from .models import Batch, InventoryTransaction, Label


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'batch_number', 'quantity',
        'expiry_date', 'cost_price', 'sell_price', 'created_at'
    ]
    list_filter = ['product__business', 'location', 'expiry_date']
    search_fields = ['product__name', 'batch_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'expiry_date'


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ['batch', 'type', 'quantity', 'reason', 'user', 'created_at']
    list_filter = ['type', 'reason', 'created_at']
    search_fields = ['batch__product__name', 'reference']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['batch', 'qr_code', 'printed_at', 'printed_by']
    list_filter = ['printed_at']
    search_fields = ['batch__product__name', 'qr_code']
