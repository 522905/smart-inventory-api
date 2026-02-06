from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q, F, Min
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.products.models import Product
from apps.inventory.models import Batch, InventoryTransaction
from apps.inventory.serializers import BatchSerializer
from apps.products.serializers import ProductSerializer


class DashboardView(APIView):
    """
    Business-type specific dashboard with key metrics.
    Returns common metrics plus specialized metrics based on business type.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        description='Get dashboard metrics for the business (varies by business type)',
        responses={200: dict}
    )
    def get(self, request):
        business = request.user.business
        today = timezone.now().date()

        # Common metrics for all business types
        common_metrics = self._get_common_metrics(business, today)

        # Business-type specific metrics
        business_type = business.type
        if business_type == 'pharmacy':
            specific_metrics = self._get_pharmacy_metrics(business, today)
        elif business_type == 'retail':
            specific_metrics = self._get_retail_metrics(business, today)
        elif business_type == 'warehouse':
            specific_metrics = self._get_warehouse_metrics(business, today)
        elif business_type == 'distributor':
            specific_metrics = self._get_distributor_metrics(business, today)
        else:
            specific_metrics = {}

        return Response({
            'business_type': business_type,
            'business_name': business.name,
            **common_metrics,
            **specific_metrics,
        })

    def _get_common_metrics(self, business, today):
        """Metrics common to all business types."""
        products = Product.objects.filter(business=business)
        batches = Batch.objects.filter(product__business=business)

        # Total products
        total_products = products.count()

        # Stock value
        stock_value = batches.filter(quantity__gt=0).aggregate(
            total=Sum(F('quantity') * F('cost_price'))
        )['total'] or 0

        # Low stock count
        low_stock_count = sum(1 for p in products if p.is_low_stock)

        # Expiring soon (30 days)
        expiring_deadline = today + timedelta(days=30)
        expiring_soon = batches.filter(
            expiry_date__lte=expiring_deadline,
            expiry_date__gte=today,
            quantity__gt=0
        ).count()

        # Out of stock products
        out_of_stock = sum(1 for p in products if p.total_stock == 0)

        # Total stock quantity
        total_stock = batches.aggregate(total=Sum('quantity'))['total'] or 0

        return {
            'total_products': total_products,
            'stock_value': float(stock_value),
            'low_stock_count': low_stock_count,
            'expiring_soon': expiring_soon,
            'out_of_stock': out_of_stock,
            'total_stock': total_stock,
        }

    def _get_pharmacy_metrics(self, business, today):
        """Pharmacy-specific metrics: expiry alerts, batch tracking."""
        batches = Batch.objects.filter(product__business=business, quantity__gt=0)

        # Expiring in 7 days (critical for pharmacy)
        critical_deadline = today + timedelta(days=7)
        expiring_in_7_days = batches.filter(
            expiry_date__lte=critical_deadline,
            expiry_date__gte=today
        ).count()

        # Expired batches with stock
        expired_batches = batches.filter(expiry_date__lt=today).count()

        # Batches needing attention (expiring in 30 days)
        batch_alerts = batches.filter(
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gte=today
        ).select_related('product')[:5]

        batch_alerts_data = [
            {
                'id': str(b.id),
                'product_name': b.product.name,
                'batch_number': b.batch_number,
                'expiry_date': b.expiry_date.isoformat(),
                'quantity': b.quantity,
                'days_until_expiry': (b.expiry_date - today).days,
            }
            for b in batch_alerts
        ]

        # Total batches being tracked
        total_batches = batches.count()

        return {
            'expiring_in_7_days': expiring_in_7_days,
            'expired_batches': expired_batches,
            'batch_alerts': batch_alerts_data,
            'total_batches': total_batches,
            'controlled_substances': 0,  # Placeholder for future implementation
        }

    def _get_retail_metrics(self, business, today):
        """Retail-specific metrics: sales, profit margins, top sellers."""
        batches = Batch.objects.filter(product__business=business)

        # Today's transactions
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_transactions = InventoryTransaction.objects.filter(
            batch__product__business=business,
            created_at__gte=today_start
        )

        # Today's sales (outward transactions)
        today_sales_qty = today_transactions.filter(type='OUT').aggregate(
            total=Sum('quantity')
        )['total'] or 0

        # Calculate today's sales value
        today_outward = today_transactions.filter(type='OUT')
        today_sales_value = sum(
            t.quantity * (t.batch.sell_price or t.batch.cost_price or 0)
            for t in today_outward.select_related('batch')
        )

        # Potential profit margin (sell_price - cost_price) / sell_price
        batches_with_prices = batches.filter(
            sell_price__gt=0, cost_price__gt=0, quantity__gt=0
        )
        if batches_with_prices.exists():
            total_cost = batches_with_prices.aggregate(
                total=Sum(F('quantity') * F('cost_price'))
            )['total'] or 0
            total_sell = batches_with_prices.aggregate(
                total=Sum(F('quantity') * F('sell_price'))
            )['total'] or 0
            if total_sell > 0:
                profit_margin = round(((total_sell - total_cost) / total_sell) * 100, 1)
            else:
                profit_margin = 0
        else:
            profit_margin = 0

        # Top selling products (by outward quantity in last 30 days)
        last_30_days = today - timedelta(days=30)
        top_selling = InventoryTransaction.objects.filter(
            batch__product__business=business,
            type='OUT',
            created_at__date__gte=last_30_days
        ).values(
            'batch__product__id',
            'batch__product__name'
        ).annotate(
            total_sold=Sum('quantity')
        ).order_by('-total_sold')[:5]

        top_selling_data = [
            {
                'product_id': str(item['batch__product__id']),
                'product_name': item['batch__product__name'],
                'total_sold': item['total_sold'],
            }
            for item in top_selling
        ]

        return {
            'today_sales_qty': today_sales_qty,
            'today_sales_value': float(today_sales_value),
            'profit_margin': profit_margin,
            'top_selling_products': top_selling_data,
        }

    def _get_warehouse_metrics(self, business, today):
        """Warehouse-specific metrics: locations, storage utilization."""
        from apps.business.models import Location

        locations = Location.objects.filter(business=business)
        batches = Batch.objects.filter(product__business=business)

        # Location utilization
        location_stats = []
        for loc in locations:
            loc_batches = batches.filter(location=loc)
            stock_qty = loc_batches.aggregate(total=Sum('quantity'))['total'] or 0
            stock_value = loc_batches.aggregate(
                total=Sum(F('quantity') * F('cost_price'))
            )['total'] or 0

            location_stats.append({
                'id': str(loc.id),
                'name': loc.name,
                'is_default': loc.is_default,
                'stock_quantity': stock_qty,
                'stock_value': float(stock_value),
                'batch_count': loc_batches.count(),
            })

        # Total locations
        total_locations = locations.count()

        # Pending transfers (placeholder)
        pending_transfers = 0

        return {
            'total_locations': total_locations,
            'location_utilization': location_stats,
            'pending_transfers': pending_transfers,
            'storage_zones': total_locations,  # Alias for now
        }

    def _get_distributor_metrics(self, business, today):
        """Distributor-specific metrics: orders, transfers, deliveries."""
        batches = Batch.objects.filter(product__business=business)

        # Recent outward transactions as "orders"
        last_7_days = today - timedelta(days=7)
        recent_outward = InventoryTransaction.objects.filter(
            batch__product__business=business,
            type='OUT',
            created_at__date__gte=last_7_days
        )

        # Group by reason
        orders_by_reason = recent_outward.values('reason').annotate(
            count=Count('id'),
            total_qty=Sum('quantity')
        ).order_by('-count')

        orders_data = [
            {
                'reason': item['reason'],
                'count': item['count'],
                'total_quantity': item['total_qty'],
            }
            for item in orders_by_reason
        ]

        # Total orders (outward transactions)
        pending_orders = recent_outward.filter(reason='sale').count()

        # Active transfers (using 'transfer' reason)
        active_transfers = recent_outward.filter(reason='transfer').count()

        return {
            'pending_orders': pending_orders,
            'active_transfers': active_transfers,
            'orders_by_reason': orders_data,
            'delivery_schedule': [],  # Placeholder for future
        }


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
