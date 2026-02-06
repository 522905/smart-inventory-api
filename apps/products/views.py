from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter

from core.mixins import BusinessFilterMixin
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductCreateSerializer,
)


class ProductFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    low_stock = filters.BooleanFilter(method='filter_low_stock')

    class Meta:
        model = Product
        fields = ['category', 'is_active']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            models.Q(name__icontains=value) |
            models.Q(barcode__icontains=value) |
            models.Q(sku__icontains=value)
        )

    def filter_low_stock(self, queryset, name, value):
        if value:
            # This is a simplified version; actual implementation would need annotation
            return queryset.filter(batches__quantity__lte=models.F('min_stock'))
        return queryset


@extend_schema_view(
    list=extend_schema(description='List all categories'),
    retrieve=extend_schema(description='Get category details'),
    create=extend_schema(description='Create a new category'),
    update=extend_schema(description='Update a category'),
    destroy=extend_schema(description='Delete a category'),
)
class CategoryViewSet(BusinessFilterMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.business)


@extend_schema_view(
    list=extend_schema(
        description='List all products',
        parameters=[
            OpenApiParameter(name='search', description='Search by name, barcode, or SKU'),
            OpenApiParameter(name='category', description='Filter by category ID'),
            OpenApiParameter(name='low_stock', description='Filter low stock products', type=bool),
        ]
    ),
    retrieve=extend_schema(description='Get product details'),
    create=extend_schema(description='Create a new product'),
    update=extend_schema(description='Update a product'),
    destroy=extend_schema(description='Delete a product'),
)
class ProductViewSet(BusinessFilterMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    permission_classes = [IsAuthenticated]
    filterset_class = ProductFilter
    search_fields = ['name', 'barcode', 'sku']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateSerializer
        return ProductSerializer

    @extend_schema(
        description='Get product by barcode',
        responses={200: ProductSerializer, 404: None}
    )
    @action(detail=False, methods=['get'], url_path='by-barcode/(?P<barcode>[^/.]+)')
    def by_barcode(self, request, barcode=None):
        try:
            product = self.get_queryset().get(barcode=barcode)
            serializer = ProductSerializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response(
                {'detail': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        description='Fast product autocomplete for search',
        parameters=[
            OpenApiParameter(name='q', description='Search query (name or barcode)', required=True),
        ],
        responses={200: list}
    )
    @action(detail=False, methods=['get'])
    def autocomplete(self, request):
        """
        Fast product autocomplete returning minimal data.
        Returns id, name, barcode, stock for up to 10 matches.
        """
        query = request.query_params.get('q', '').strip()
        if len(query) < 1:
            return Response([])

        products = self.get_queryset().filter(
            models.Q(name__icontains=query) |
            models.Q(barcode__icontains=query)
        ).select_related('category')[:10]

        results = [
            {
                'id': str(p.id),
                'name': p.name,
                'barcode': p.barcode,
                'stock': p.total_stock,
                'unit': p.unit,
                'category_name': p.category.name if p.category else None,
            }
            for p in products
        ]

        return Response(results)
