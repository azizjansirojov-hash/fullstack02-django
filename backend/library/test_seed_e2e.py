"""Tests for seed_e2e management command production guard."""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class SeedE2eCommandTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_when_debug_false(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('seed_e2e')
        self.assertIn('DEBUG', str(ctx.exception))

    @override_settings(DEBUG=True)
    def test_succeeds_when_debug_true(self):
        out = StringIO()
        call_command('seed_e2e', stdout=out)
        self.assertIn('seed_e2e ok', out.getvalue())
