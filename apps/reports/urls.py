from django.urls import path
from .views import (
    DashboardView,
    StockSummaryView,
    ExpiryAlertView,
    LowStockView,
    MovementReportView,
)

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('reports/stock-summary/', StockSummaryView.as_view(), name='stock-summary'),
    path('reports/expiry-alert/', ExpiryAlertView.as_view(), name='expiry-alert'),
    path('reports/low-stock/', LowStockView.as_view(), name='low-stock'),
    path('reports/movement/', MovementReportView.as_view(), name='movement-report'),
]
