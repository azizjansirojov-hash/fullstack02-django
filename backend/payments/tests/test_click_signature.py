"""Click MD5 sign_string vectors.

Formula source: Click Shop API documentation (docs.click.uz) —
Prepare (7-arg) and Complete (8-arg) MD5 concatenations.
Official docs do not publish fixed hex digests for a sample secret; these
vectors are computed from the published formula with a fixed secret and
cross-checked against an independent hashlib.md5 of the same concatenation.
"""

import hashlib

from django.test import SimpleTestCase

from payments.providers.click import click_sign_complete, click_sign_prepare, verify_click_sign


class ClickSignStringTests(SimpleTestCase):
    SECRET = 'aSecretKeyFromClickDocsStyle'

    def test_prepare_matches_published_formula(self):
        # docs.click.uz Prepare:
        # md5(click_trans_id + service_id + secret_key + merchant_trans_id
        #     + amount + action + sign_time)
        click_trans_id = '3001234567'
        service_id = '94048'
        merchant_trans_id = 'invoice_4521'
        amount = '499000'
        action = '0'
        sign_time = '2026-05-05 14:30:00'
        raw = (
            f'{click_trans_id}{service_id}{self.SECRET}{merchant_trans_id}'
            f'{amount}{action}{sign_time}'
        )
        expected = hashlib.md5(raw.encode('utf-8')).hexdigest()
        got = click_sign_prepare(
            click_trans_id=click_trans_id,
            service_id=service_id,
            secret_key=self.SECRET,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            action=action,
            sign_time=sign_time,
        )
        self.assertEqual(got, expected)
        self.assertTrue(verify_click_sign(expected, got))

    def test_complete_matches_published_formula(self):
        # docs.click.uz Complete adds merchant_prepare_id before amount.
        click_trans_id = '3001234567'
        service_id = '94048'
        merchant_trans_id = 'invoice_4521'
        merchant_prepare_id = '987654321'
        amount = '499000'
        action = '1'
        sign_time = '2026-05-05 14:31:12'
        raw = (
            f'{click_trans_id}{service_id}{self.SECRET}{merchant_trans_id}'
            f'{merchant_prepare_id}{amount}{action}{sign_time}'
        )
        expected = hashlib.md5(raw.encode('utf-8')).hexdigest()
        got = click_sign_complete(
            click_trans_id=click_trans_id,
            service_id=service_id,
            secret_key=self.SECRET,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action=action,
            sign_time=sign_time,
        )
        self.assertEqual(got, expected)
        self.assertFalse(verify_click_sign(expected, 'deadbeef'))
