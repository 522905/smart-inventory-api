from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter

from core.mixins import BusinessFilterMixin
from .models import Batch, InventoryTransaction, Label
from .serializers import (
    BatchSerializer,
    BatchCreateSerializer,
    TransactionSerializer,
    InwardSerializer,
    OutwardSerializer,
    AdjustmentSerializer,
    LabelSerializer,
    QuickInSerializer,
    QuickOutSerializer,
)


class BatchFilter(filters.FilterSet):
    product = filters.UUIDFilter(field_name='product_id')
    location = filters.UUIDFilter(field_name='location_id')
    expiring = filters.BooleanFilter(method='filter_expiring')
    days = filters.NumberFilter(method='filter_by_days')

    class Meta:
        model = Batch
        fields = ['product', 'location']

    def filter_expiring(self, queryset, name, value):
        if value:
            days = self.data.get('days', 30)
            deadline = timezone.now().date() + timedelta(days=int(days))
            return queryset.filter(
                expiry_date__lte=deadline,
                expiry_date__gte=timezone.now().date(),
                quantity__gt=0
            )
        return queryset

    def filter_by_days(self, queryset, name, value):
        return queryset


@extend_schema_view(
    list=extend_schema(
        description='List all batches',
        parameters=[
            OpenApiParameter(name='product', description='Filter by product ID'),
            OpenApiParameter(name='location', description='Filter by location ID'),
            OpenApiParameter(name='expiring', description='Filter expiring batches', type=bool),
            OpenApiParameter(name='days', description='Days until expiry (default 30)'),
        ]
    ),
    retrieve=extend_schema(description='Get batch details'),
    create=extend_schema(description='Create a new batch with initial stock'),
    update=extend_schema(description='Update batch details'),
)
class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.select_related('product', 'location').all()
    permission_classes = [IsAuthenticated]
    filterset_class = BatchFilter

    def get_serializer_class(self):
        if self.action in ['create']:
            return BatchCreateSerializer
        return BatchSerializer

    def create(self, request, *args, **kwargs):
        """Override create to return full BatchSerializer response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = serializer.save()
        # Return full batch data with product info
        response_serializer = BatchSerializer(batch)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.business:
            queryset = queryset.filter(product__business=user.business)
        return queryset

    @extend_schema(
        description='Get expiring batches',
        parameters=[
            OpenApiParameter(name='days', description='Days until expiry', default=30),
        ]
    )
    @action(detail=False, methods=['get'])
    def expiring(self, request):
        days = int(request.query_params.get('days', 30))
        deadline = timezone.now().date() + timedelta(days=days)

        batches = self.get_queryset().filter(
            expiry_date__lte=deadline,
            expiry_date__gte=timezone.now().date(),
            quantity__gt=0
        ).order_by('expiry_date')

        serializer = BatchSerializer(batches, many=True)
        return Response(serializer.data)


class TransactionFilter(filters.FilterSet):
    batch = filters.UUIDFilter(field_name='batch_id')
    product = filters.UUIDFilter(field_name='batch__product_id')
    type = filters.ChoiceFilter(choices=InventoryTransaction.TYPE_CHOICES)
    start_date = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = InventoryTransaction
        fields = ['batch', 'product', 'type']


@extend_schema_view(
    list=extend_schema(
        description='List all inventory transactions',
        parameters=[
            OpenApiParameter(name='batch', description='Filter by batch ID'),
            OpenApiParameter(name='product', description='Filter by product ID'),
            OpenApiParameter(name='type', description='Filter by type (IN/OUT/ADJUST)'),
            OpenApiParameter(name='start_date', description='Start date filter'),
            OpenApiParameter(name='end_date', description='End date filter'),
        ]
    ),
)
class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryTransaction.objects.select_related(
        'batch', 'batch__product', 'user'
    ).all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TransactionFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.business:
            queryset = queryset.filter(batch__product__business=user.business)
        return queryset


class InwardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InwardSerializer,
        responses={201: TransactionSerializer},
        description='Record stock inward'
    )
    def post(self, request):
        serializer = InwardSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        return Response(
            TransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED
        )


class OutwardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=OutwardSerializer,
        responses={201: TransactionSerializer},
        description='Record stock outward with FEFO'
    )
    def post(self, request):
        serializer = OutwardSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        return Response(
            TransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED
        )


class AdjustView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AdjustmentSerializer,
        responses={201: TransactionSerializer},
        description='Record stock adjustment'
    )
    def post(self, request):
        serializer = AdjustmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        return Response(
            TransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED
        )


class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.select_related('batch', 'batch__product').all()
    serializer_class = LabelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.business:
            queryset = queryset.filter(batch__product__business=user.business)
        return queryset


class QuickInView(APIView):
    """
    Quick Stock In: Create batch + record inward in one API call.
    Combines batch creation and stock inward for faster workflow.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=QuickInSerializer,
        responses={201: dict},
        description='Quick stock in: create batch and record inward in one call'
    )
    def post(self, request):
        serializer = QuickInSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        batch = result['batch']
        txn = result['transaction']

        return Response({
            'message': 'Stock received successfully',
            'batch': BatchSerializer(batch).data,
            'transaction': TransactionSerializer(txn).data,
        }, status=status.HTTP_201_CREATED)


class QuickOutView(APIView):
    """
    Quick Stock Out: Auto-select batches using FEFO and deduct stock.
    Automatically picks batches with earliest expiry dates first.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=QuickOutSerializer,
        responses={201: dict},
        description='Quick stock out: auto-select batches (FEFO) and deduct stock'
    )
    def post(self, request):
        serializer = QuickOutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response({
            'message': 'Stock issued successfully',
            'product_id': str(result['product'].id),
            'product_name': result['product'].name,
            'total_deducted': result['total_deducted'],
            'batches_affected': result['batches_affected'],
            'transactions': TransactionSerializer(result['transactions'], many=True).data,
        }, status=status.HTTP_201_CREATED)
