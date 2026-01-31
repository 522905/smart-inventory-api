from rest_framework import serializers


class BusinessFilterMixin:
    """
    Mixin to filter querysets by the user's business.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            if hasattr(queryset.model, 'business'):
                queryset = queryset.filter(business=self.request.user.business)
            elif hasattr(queryset.model, 'business_id'):
                queryset = queryset.filter(business_id=self.request.user.business_id)
        return queryset


class AuditMixin(serializers.ModelSerializer):
    """
    Mixin to automatically set created_by and updated_by fields.
    """
    def create(self, validated_data):
        if hasattr(self.Meta.model, 'created_by'):
            validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if hasattr(self.Meta.model, 'updated_by'):
            validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)
