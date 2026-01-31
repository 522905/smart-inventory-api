from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.products.models import Product
from apps.inventory.models import Batch, InventoryTransaction
from apps.inventory.serializers import BatchSerializer
from apps.products.serializers import ProductSerializer


class StockSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description='Get stock summary for the business',
        responses={200: dict}
    )
    def get(self, request):
        business = request.user.business

        # Total products
        total_products = Product.objects.filter(business=business).count()

        # Total stock value
        batches = Batch.objects.filter(product__business=business)
        total_stock_value = batches.aggregate(
            total=Sum(F('quantity') * F('cost_price'))
        )['total'] or 0

        # Total items in stock
        total_items = batches.aggregate(total=Sum('quantity'))['total'] or 0

        # Low stock products
        low_stock_count = 0
        for product in Product.objects.filter(business=business):
            if product.is_low_stock:
                low_stock_count += 1

        # Expiring soon (next 30 days)
        deadline = timezone.now().date() + timedelta(days=30)
        expiring_count = batches.filter(
            expiry_date__lte=deadline,
            expiry_date__gte=timezone.now().date(),
            quantity__gt=0
        ).count()

        # Expired
        expired_count = batches.filter(
            expiry_date__lt=timezone.now().date(),
            quantity__gt=0
        ).count()

        return Response({
            'total_products': total_products,
            'total_items_in_stock': total_items,
            'total_stock_value': float(total_stock_value),
            'low_stock_products': low_stock_count,
            'expiring_soon': expiring_count,
            'expired': expired_count,
        })


class ExpiryAlertView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description='Get batches expiring soon',
        parameters=[
            OpenApiParameter(name='days', description='Days until expiry', default=30),
        ],
        responses={200: BatchSerializer(many=True)}
    )
    def get(self, request):
        business = request.user.business
        days = int(request.query_params.get('days', 30))
        deadline = timezone.now().date() + timedelta(days=days)

        batches = Batch.objects.filter(
            product__business=business,
            expiry_date__lte=deadline,
            expiry_date__gte=timezone.now().date(),
            quantity__gt=0
        ).select_related('product', 'location').order_by('expiry_date')

        serializer = BatchSerializer(batches, many=True)
        return Response({'results': serializer.data})


class LowStockView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description='Get products with low stock',
        responses={200: ProductSerializer(many=True)}
    )
    def get(self, request):
        business = request.user.business

        # Get products with calculated stock
        products = Product.objects.filter(
            business=business,
            is_active=True
        ).select_related('category')

        low_stock_products = [p for p in products if p.is_low_stock]

        serializer = ProductSerializer(low_stock_products, many=True)
        return Response({'results': serializer.data})


class MovementReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description='Get stock movement report',
        parameters=[
            OpenApiParameter(name='product', description='Filter by product ID'),
            OpenApiParameter(name='start_date', description='Start date (YYYY-MM-DD)'),
            OpenApiParameter(name='end_date', description='End date (YYYY-MM-DD)'),
        ],
        responses={200: dict}
    )
    def get(self, request):
        business = request.user.business
        product_id = request.query_params.get('product')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # Base queryset
        transactions = InventoryTransaction.objects.filter(
            batch__product__business=business
        )

        # Apply filters
        if product_id:
            transactions = transactions.filter(batch__product_id=product_id)
        if start_date:
            transactions = transactions.filter(created_at__date__gte=start_date)
        if end_date:
            transactions = transactions.filter(created_at__date__lte=end_date)

        # Calculate totals
        inward = transactions.filter(type='IN').aggregate(
            total=Sum('quantity')
        )['total'] or 0

        outward = transactions.filter(type='OUT').aggregate(
            total=Sum('quantity')
        )['total'] or 0

        adjustments = transactions.filter(type='ADJUST').aggregate(
            total=Sum('quantity')
        )['total'] or 0

        # Group by reason for outward
        outward_by_reason = transactions.filter(type='OUT').values('reason').annotate(
            total=Sum('quantity')
        ).order_by('-total')

        return Response({
            'summary': {
                'total_inward': inward,
                'total_outward': outward,
                'total_adjustments': adjustments,
                'net_change': inward - outward + adjustments,
            },
            'outward_by_reason': list(outward_by_reason),
            'transaction_count': transactions.count(),
        })
