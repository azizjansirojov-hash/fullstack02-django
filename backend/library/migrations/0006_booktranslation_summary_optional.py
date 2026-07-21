from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0005_booktranslation_why_read_optional'),
    ]

    operations = [
        migrations.AlterField(
            model_name='booktranslation',
            name='summary',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Optional short blurb for catalog cards.',
            ),
        ),
    ]
