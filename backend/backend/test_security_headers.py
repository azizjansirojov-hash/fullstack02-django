"""CSP and related browser-hardening headers."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from backend.security_headers import PERMISSIONS_POLICY

User = get_user_model()


class BrowserHardeningHeaderTests(TestCase):
    def test_legal_page_sends_enforcing_csp(self):
        response = self.client.get(reverse('terms'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Content-Security-Policy-Report-Only', response)
        csp = response['Content-Security-Policy']
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("'unsafe-inline'", csp.split('script-src')[1].split(';')[0])
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertIn("worker-src 'self' blob:", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("form-action 'self'", csp)
        self.assertNotIn('https://fonts.googleapis.com', csp)
        self.assertNotIn('https://fonts.gstatic.com', csp)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(
            response['Referrer-Policy'],
            'strict-origin-when-cross-origin',
        )
        self.assertEqual(response['Permissions-Policy'], PERMISSIONS_POLICY)

    def test_rights_report_has_no_inline_script(self):
        response = self.client.get(reverse('rights-report'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('<script>', html)
        self.assertIn('legal/rights-report.js', html)
        csp = response['Content-Security-Policy']
        script_src = csp.split('script-src')[1].split(';')[0]
        self.assertNotIn('unsafe-inline', script_src)

    def test_admin_login_uses_self_style_src(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        csp = response['Content-Security-Policy']
        style_src = csp.split('style-src')[1].split(';')[0]
        self.assertNotIn("'unsafe-inline'", style_src)
        script_src = csp.split('script-src')[1].split(';')[0]
        self.assertNotIn('unsafe-inline', script_src)
        self.assertNotIn('unsafe-eval', script_src)

    def test_admin_changelist_and_change_form_under_admin_csp(self):
        User.objects.create_superuser(
            username='cspadmin',
            email='cspadmin@example.com',
            password='Str0ng-Admin-Passw0rd!',
        )
        self.client.login(username='cspadmin', password='Str0ng-Admin-Passw0rd!')
        changelist = self.client.get('/admin/library/book/')
        self.assertEqual(changelist.status_code, 200)
        style_src = changelist['Content-Security-Policy'].split('style-src')[1].split(';')[0]
        self.assertNotIn("'unsafe-inline'", style_src)
        html = changelist.content.decode()
        self.assertNotIn('<style>', html)
        add_form = self.client.get('/admin/library/book/add/')
        self.assertEqual(add_form.status_code, 200)
        self.assertIn("script-src 'self'", add_form['Content-Security-Policy'])
