# Generated manually — purge English and Russian book translations.

from django.db import migrations


def delete_non_uzbek_translations(apps, schema_editor):
    BookTranslation = apps.get_model('library', 'BookTranslation')
    BookTranslation.objects.exclude(language='uz').delete()


def noop_reverse(apps, schema_editor):
    # EN/RU content cannot be restored after deletion.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0003_uzbek_only_language'),
    ]

    operations = [
        migrations.RunPython(delete_non_uzbek_translations, noop_reverse),
    ]
