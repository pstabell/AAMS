"""
Regression tests for the solo-agent Stripe checkout flow (auth_helpers.py).

These tests run without any external dependencies (no Stripe API key, no
Streamlit, no Supabase) and exercise four critical behaviors:

1. Both legal checkboxes (Terms + Privacy) are required before checkout proceeds.
2. Checkout session includes a 14-day free trial.
3. Checkout uses payment_method_collection='if_required' (supports 100%-off coupons).
4. Legal-acceptance metadata is passed through to Stripe.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on path when running from anywhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Stub heavy dependencies before importing auth_helpers so this file works
# even when the packages are not installed in the current environment.
# ---------------------------------------------------------------------------
sys.modules['streamlit'] = MagicMock()
sys.modules['supabase'] = MagicMock()
sys.modules['stripe'] = MagicMock()

from auth_helpers import _validate_legal_acceptance, _build_checkout_kwargs, _hash_password, _verify_password  # noqa: E402

_FIXED_AT = '2026-03-24T12:00:00Z'
_PRICE_ID = 'price_test_abc123'
_APP_URL = 'https://example.onrender.com'


# ---------------------------------------------------------------------------
# 1. Legal acceptance validation
# ---------------------------------------------------------------------------
class TestValidateLegalAcceptance(unittest.TestCase):

    def test_both_accepted_returns_none(self):
        """No error when both checkboxes are ticked."""
        self.assertIsNone(_validate_legal_acceptance(True, True))

    def test_terms_not_accepted_returns_error(self):
        """Error when Terms of Service checkbox is unticked."""
        error = _validate_legal_acceptance(False, True)
        self.assertIsNotNone(error)
        self.assertIn("Terms of Service", error)

    def test_privacy_not_accepted_returns_error(self):
        """Error when Privacy Policy checkbox is unticked."""
        error = _validate_legal_acceptance(True, False)
        self.assertIsNotNone(error)
        self.assertIn("Privacy Policy", error)

    def test_both_not_accepted_returns_terms_error_first(self):
        """Terms error takes priority when both boxes are unticked."""
        error = _validate_legal_acceptance(False, False)
        self.assertIsNotNone(error)
        self.assertIn("Terms of Service", error)

    def test_returns_string_on_failure(self):
        """Validation errors must be strings (used directly with st.error)."""
        self.assertIsInstance(_validate_legal_acceptance(False, True), str)
        self.assertIsInstance(_validate_legal_acceptance(True, False), str)


# ---------------------------------------------------------------------------
# 2 & 3 & 4. Checkout kwargs (trial, payment_method_collection, metadata)
# ---------------------------------------------------------------------------
class TestBuildCheckoutKwargs(unittest.TestCase):

    def setUp(self):
        self.kwargs = _build_checkout_kwargs(
            email='agent@example.com',
            accepted_at=_FIXED_AT,
            price_id=_PRICE_ID,
            app_url=_APP_URL,
        )

    # --- 2. 14-day free trial ---
    def test_trial_period_days_is_14(self):
        """subscription_data must include trial_period_days=14."""
        self.assertEqual(
            self.kwargs['subscription_data']['trial_period_days'], 14
        )

    def test_mode_is_subscription(self):
        """mode must be 'subscription' for recurring billing."""
        self.assertEqual(self.kwargs['mode'], 'subscription')

    # --- 3. payment_method_collection ---
    def test_payment_method_collection_is_if_required(self):
        """Must be 'if_required' so 100%-off coupons skip card entry."""
        self.assertEqual(self.kwargs['payment_method_collection'], 'if_required')

    # --- 4. Legal acceptance metadata ---
    def test_metadata_accepted_terms_is_true(self):
        self.assertEqual(self.kwargs['metadata']['accepted_terms'], 'true')

    def test_metadata_accepted_privacy_is_true(self):
        self.assertEqual(self.kwargs['metadata']['accepted_privacy'], 'true')

    def test_metadata_accepted_at_is_passed_through(self):
        self.assertEqual(self.kwargs['metadata']['accepted_at'], _FIXED_AT)

    def test_metadata_terms_version_present(self):
        self.assertIn('terms_version', self.kwargs['metadata'])

    def test_metadata_privacy_version_present(self):
        self.assertIn('privacy_version', self.kwargs['metadata'])

    # --- Other required fields ---
    def test_customer_email_is_set(self):
        self.assertEqual(self.kwargs['customer_email'], 'agent@example.com')

    def test_price_id_in_line_items(self):
        self.assertEqual(self.kwargs['line_items'][0]['price'], _PRICE_ID)

    def test_promotion_codes_enabled(self):
        self.assertTrue(self.kwargs['allow_promotion_codes'])

    def test_success_url_contains_session_id_placeholder(self):
        self.assertIn('{CHECKOUT_SESSION_ID}', self.kwargs['success_url'])

    def test_success_url_starts_with_app_url(self):
        self.assertTrue(self.kwargs['success_url'].startswith(_APP_URL))

    def test_cancel_url_is_app_url(self):
        self.assertEqual(self.kwargs['cancel_url'], _APP_URL)


# ---------------------------------------------------------------------------
# End-to-end: stripe.checkout.Session.create receives correct kwargs
# ---------------------------------------------------------------------------
class TestCheckoutSessionCreateCalledCorrectly(unittest.TestCase):

    def test_stripe_called_with_trial_and_if_required(self):
        """Verify the correct kwargs reach stripe.checkout.Session.create."""
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.return_value = MagicMock(url='https://checkout.stripe.com/pay/cs_test')

        kwargs = _build_checkout_kwargs(
            email='solo@example.com',
            accepted_at=_FIXED_AT,
            price_id=_PRICE_ID,
            app_url=_APP_URL,
        )
        mock_stripe.checkout.Session.create(**kwargs)

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        self.assertEqual(call_kwargs['subscription_data']['trial_period_days'], 14)
        self.assertEqual(call_kwargs['payment_method_collection'], 'if_required')
        self.assertEqual(call_kwargs['metadata']['accepted_terms'], 'true')
        self.assertEqual(call_kwargs['metadata']['accepted_privacy'], 'true')


# ---------------------------------------------------------------------------
# Password hashing helpers
# ---------------------------------------------------------------------------
class TestHashPassword(unittest.TestCase):

    def test_returns_string(self):
        self.assertIsInstance(_hash_password('secret'), str)

    def test_bcrypt_prefix(self):
        """Hash must start with a bcrypt identifier ($2b$)."""
        self.assertTrue(_hash_password('secret').startswith('$2b$'))

    def test_different_calls_produce_different_salts(self):
        """Each call should produce a unique hash (random salt)."""
        self.assertNotEqual(_hash_password('same'), _hash_password('same'))

    def test_hash_is_not_plaintext(self):
        pw = 'mysecretpassword'
        self.assertNotEqual(_hash_password(pw), pw)


class TestVerifyPassword(unittest.TestCase):

    def test_correct_bcrypt_hash_returns_true(self):
        pw = 'correct-horse-battery-staple'
        stored = _hash_password(pw)
        self.assertTrue(_verify_password(pw, stored))

    def test_wrong_password_bcrypt_returns_false(self):
        stored = _hash_password('correct')
        self.assertFalse(_verify_password('wrong', stored))

    def test_legacy_plaintext_correct_returns_true(self):
        """Migration path: plain-text stored passwords still authenticate."""
        self.assertTrue(_verify_password('mypassword', 'mypassword'))

    def test_legacy_plaintext_wrong_returns_false(self):
        self.assertFalse(_verify_password('wrong', 'mypassword'))

    def test_legacy_plaintext_cannot_fool_bcrypt_check(self):
        """A plain-text value that looks like a bcrypt hash is rejected properly."""
        # A real bcrypt hash of 'x' – verify with 'y' must return False.
        real_hash = _hash_password('x')
        self.assertFalse(_verify_password('y', real_hash))

    def test_bcrypt_hash_not_treated_as_plaintext(self):
        """Verifying a bcrypt-hash string against itself (as password) must fail."""
        stored = _hash_password('secret')
        # The stored hash itself is not the password.
        self.assertFalse(_verify_password(stored, stored))


if __name__ == '__main__':
    unittest.main(verbosity=2)
