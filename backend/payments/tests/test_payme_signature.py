"""Payme Basic Auth verification.

Source: Payme Merchant API uses HTTP Basic Auth with login ``Paycom`` and
password = merchant cash-register key
(https://developer.help.paycom.uz/protokol-merchant-api/).
"""

import base64

from django.test import SimpleTestCase

from payments.providers.payme import verify_payme_basic_auth


class PaymeBasicAuthTests(SimpleTestCase):
    def test_valid_paycom_credentials(self):
        key = 'test-merchant-key-vector'
        token = base64.b64encode(f'Paycom:{key}'.encode('utf-8')).decode('ascii')
        self.assertTrue(verify_payme_basic_auth(f'Basic {token}', key))

    def test_rejects_wrong_password(self):
        token = base64.b64encode(b'Paycom:wrong').decode('ascii')
        self.assertFalse(verify_payme_basic_auth(f'Basic {token}', 'correct-key'))

    def test_rejects_wrong_login(self):
        key = 'test-merchant-key-vector'
        token = base64.b64encode(f'Other:{key}'.encode('utf-8')).decode('ascii')
        self.assertFalse(verify_payme_basic_auth(f'Basic {token}', key))

    def test_rejects_missing_header(self):
        self.assertFalse(verify_payme_basic_auth(None, 'key'))
        self.assertFalse(verify_payme_basic_auth('', 'key'))
        self.assertFalse(verify_payme_basic_auth('Bearer x', 'key'))
