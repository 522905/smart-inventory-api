from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema_view, extend_schema

from core.mixins import BusinessFilterMixin
from .models import Business, Location
from .serializers import BusinessSerializer, LocationSerializer


@extend_schema_view(
    list=extend_schema(description='List all locations'),
    retrieve=extend_schema(description='Get location details'),
    create=extend_schema(description='Create a new location'),
    update=extend_schema(description='Update a location'),
    destroy=extend_schema(description='Delete a location'),
)
class LocationViewSet(BusinessFilterMixin, viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.business)
