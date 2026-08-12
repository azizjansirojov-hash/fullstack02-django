# Generated manually for PaymentTransaction

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('library', '0024_readingprogress_finished_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'provider',
                    models.CharField(
                        choices=[('payme', 'Payme'), ('click', 'Click')],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                (
                    'provider_transaction_id',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default='',
                        help_text='Gateway-side transaction id once the provider creates it.',
                        max_length=128,
                    ),
                ),
                (
                    'amount',
                    models.PositiveIntegerField(
                        help_text='Amount in tiyin (UZS minor units), snapshotted at checkout.',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('created', 'Created'),
                            ('pending', 'Pending'),
                            ('paid', 'Paid'),
                            ('cancelled', 'Cancelled'),
                            ('failed', 'Failed'),
                        ],
                        db_index=True,
                        default='created',
                        max_length=16,
                    ),
                ),
                ('raw_payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                (
                    'book',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='payment_transactions',
                        to='library.book',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='payment_transactions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='paymenttransaction',
            index=models.Index(
                fields=['provider', 'provider_transaction_id'],
                name='pay_tx_provider_ptid_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='paymenttransaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status__in', ['created', 'pending'])),
                fields=('user', 'book'),
                name='uniq_active_payment_per_user_book',
            ),
        ),
    ]
