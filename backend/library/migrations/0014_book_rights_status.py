# Generated manually for bookstore rights clearance.

from django.db import migrations, models


def set_existing_books_licensed(apps, schema_editor):
    Book = apps.get_model('library', 'Book')
    Book.objects.all().update(rights_status='licensed')


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0013_readingprogress_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='rights_status',
            field=models.CharField(
                choices=[
                    ('unset', 'Not set (blocked)'),
                    ('public_domain', 'Public domain'),
                    ('licensed', 'Licensed for sale'),
                    ('pending_clearance', 'Pending clearance'),
                ],
                db_index=True,
                default='unset',
                help_text=(
                    'Bookstore rights clearance. Public domain or licensed required '
                    'before PDF/TTS generation and publishing.'
                ),
                max_length=32,
            ),
        ),
        migrations.RunPython(set_existing_books_licensed, migrations.RunPython.noop),
    ]
