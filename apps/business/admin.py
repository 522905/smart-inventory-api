from django.contrib import admin
from .models import Business, Location


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'phone', 'created_at']
    list_filter = ['type']
    search_fields = ['name', 'phone']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'is_default', 'created_at']
    list_filter = ['business', 'is_default']
    search_fields = ['name']
