from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BatchViewSet,
    TransactionViewSet,
    InwardView,
    OutwardView,
    AdjustView,
    LabelViewSet,
    QuickInView,
    QuickOutView,
)

router = DefaultRouter()
router.register('batches', BatchViewSet, basename='batch')
router.register('inventory/transactions', TransactionViewSet, basename='transaction')
router.register('labels', LabelViewSet, basename='label')

urlpatterns = [
    path('', include(router.urls)),
    path('inventory/inward/', InwardView.as_view(), name='inventory-inward'),
    path('inventory/outward/', OutwardView.as_view(), name='inventory-outward'),
    path('inventory/adjust/', AdjustView.as_view(), name='inventory-adjust'),
    path('inventory/quick-in/', QuickInView.as_view(), name='inventory-quick-in'),
    path('inventory/quick-out/', QuickOutView.as_view(), name='inventory-quick-out'),
]
