"""Enforce case-insensitive unique emails on auth.User (non-blank only)."""

from django.contrib.auth.models import User
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


def check_no_duplicate_emails(apps, schema_editor):
    UserModel = apps.get_model('auth', 'User')
    from django.db.models import Count
    from django.db.models.functions import Lower as LowerFn

    dupes = (
        UserModel.objects.exclude(email='')
        .annotate(email_ci=LowerFn('email'))
        .values('email_ci')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
    )
    if dupes.exists():
        samples = list(dupes[:5])
        raise RuntimeError(
            'Cannot add case-insensitive unique email constraint: '
            f'duplicate emails exist (sample={samples}). '
            'Run `python manage.py report_duplicate_emails` and clean up first.'
        )


def add_email_ci_constraint(apps, schema_editor):
    constraint = models.UniqueConstraint(
        Lower('email'),
        name='auth_user_email_ci_uniq',
        condition=~Q(email=''),
    )
    schema_editor.add_constraint(User, constraint)


def remove_email_ci_constraint(apps, schema_editor):
    constraint = models.UniqueConstraint(
        Lower('email'),
        name='auth_user_email_ci_uniq',
        condition=~Q(email=''),
    )
    schema_editor.remove_constraint(User, constraint)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(check_no_duplicate_emails, migrations.RunPython.noop),
        migrations.RunPython(add_email_ci_constraint, remove_email_ci_constraint),
    ]
