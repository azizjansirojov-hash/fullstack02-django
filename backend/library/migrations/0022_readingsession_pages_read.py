# Generated manually for Feature B week page stats.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0021_readingsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='readingsession',
            name='pages_read',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Pages advanced today (flip/pdf page index increases).',
            ),
        ),
    ]
