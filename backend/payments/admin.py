"""Django admin for payment transactions."""

from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'book',
        'provider',
        'amount',
        'status',
        'provider_transaction_id',
        'paid_at',
        'created_at',
    )
    list_filter = ('provider', 'status')
    search_fields = (
        'id',
        'user__username',
        'user__email',
        'book__slug',
        'provider_transaction_id',
    )
    readonly_fields = (
        'id',
        'user',
        'book',
        'provider',
        'provider_transaction_id',
        'amount',
        'status',
        'raw_payload',
        'created_at',
        'updated_at',
        'paid_at',
    )
    autocomplete_fields = ('user', 'book')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
