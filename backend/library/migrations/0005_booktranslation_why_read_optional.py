from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0004_delete_en_ru_translations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='booktranslation',
            name='why_read',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Optional note for the reader (not shown in admin).',
            ),
        ),
    ]
