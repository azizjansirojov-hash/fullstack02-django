"""URL routes for payment checkout and provider webhooks."""

from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/', views.CheckoutAPIView.as_view(), name='checkout'),
    path(
        'transactions/<uuid:transaction_id>/',
        views.TransactionStatusAPIView.as_view(),
        name='transaction-status',
    ),
    path('payme/webhook/', views.PaymeWebhookAPIView.as_view(), name='payme-webhook'),
    path('click/prepare/', views.ClickPrepareAPIView.as_view(), name='click-prepare'),
    path('click/complete/', views.ClickCompleteAPIView.as_view(), name='click-complete'),
]
