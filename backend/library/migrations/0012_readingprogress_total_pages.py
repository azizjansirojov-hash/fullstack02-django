from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0011_generation_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='readingprogress',
            name='total_pages',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Last known total page count for flip/pdf (for progress %).',
                null=True,
            ),
        ),
    ]
