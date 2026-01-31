from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'parent', 'created_at']
    list_filter = ['business']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'category', 'barcode', 'unit', 'min_stock', 'is_active']
    list_filter = ['business', 'category', 'is_active', 'unit']
    search_fields = ['name', 'barcode', 'sku']
    readonly_fields = ['created_at', 'updated_at']
