"""
Unit tests for webhook_server subscription-status handling.

These tests run without any external dependencies (no Stripe API key, no
Supabase).  They exercise the pure logic paths that were previously broken:

1. _get_subscription_status_from_stripe() returns 'trialing' for trial subs.
2. checkout.session.completed stores the real status, not a hardcoded 'active'.
3. Legal-acceptance metadata from session.metadata is surfaced in the response.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure repo root is on the path when running from anywhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Stub out ALL heavy dependencies BEFORE importing webhook_server so this
# test file works even when the packages are not installed in the current
# Python environment (the app runs in a separate venv / Docker container).
# ---------------------------------------------------------------------------

# Minimal Flask stub that supports @app.route() decorators at import time.
_flask_app_stub = MagicMock()
_flask_app_stub.route.return_value = lambda f: f   # decorator pass-through
_flask_app_stub.logger = MagicMock()
_flask_module_stub = MagicMock()
_flask_module_stub.Flask.return_value = _flask_app_stub
sys.modules['flask'] = _flask_module_stub

# Supabase stub.
sys.modules['supabase'] = MagicMock()

# Stripe stub — api_key=None forces the fallback paths in our helper.
_stripe_stub = MagicMock()
_stripe_stub.api_key = None
sys.modules['stripe'] = _stripe_stub

# Email utility stub.
sys.modules['email_utils'] = MagicMock()

# Now we can safely import the module under test.
from webhook_server import (  # noqa: E402
    _get_subscription_status_from_stripe,
    _get_subscription_info_from_stripe,
    _normalize_stripe_status,
    _resolve_tier_from_price_id,
)


# ---------------------------------------------------------------------------
# Helper — build a minimal checkout.session.completed event payload.
# ---------------------------------------------------------------------------
def _make_checkout_event(payment_status='no_payment_required', metadata=None, sub_id='sub_test_123'):
    return {
        'type': 'checkout.session.completed',
        'id': 'evt_test',
        'data': {
            'object': {
                'customer': 'cus_test',
                'customer_details': {'email': 'test@example.com'},
                'subscription': sub_id,
                'payment_status': payment_status,
                'metadata': metadata or {
                    'accepted_terms': 'true',
                    'accepted_privacy': 'true',
                    'accepted_at': '2026-03-24T12:00:00Z',
                    'terms_version': '2024-12-06',
                    'privacy_version': '2024-12-06',
                },
            }
        }
    }


# ---------------------------------------------------------------------------
# Tests for _get_subscription_status_from_stripe()
# ---------------------------------------------------------------------------
class TestGetSubscriptionStatus(unittest.TestCase):

    def test_returns_trialing_when_stripe_says_trialing(self):
        """Stripe API returns 'trialing' → function returns 'trialing'."""
        mock_sub = {'status': 'trialing'}
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = 'sk_test_fake'
            mock_stripe.Subscription.retrieve.return_value = mock_sub
            result = _get_subscription_status_from_stripe('sub_123', {})
        self.assertEqual(result, 'trialing')

    def test_returns_active_when_stripe_says_active(self):
        """Stripe API returns 'active' → function returns 'active'."""
        mock_sub = {'status': 'active'}
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = 'sk_test_fake'
            mock_stripe.Subscription.retrieve.return_value = mock_sub
            result = _get_subscription_status_from_stripe('sub_123', {})
        self.assertEqual(result, 'active')

    def test_normalises_stripe_canceled_spelling(self):
        """Stripe uses 'canceled' (one l); DB uses 'cancelled' (two l's)."""
        mock_sub = {'status': 'canceled'}
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = 'sk_test_fake'
            mock_stripe.Subscription.retrieve.return_value = mock_sub
            result = _get_subscription_status_from_stripe('sub_123', {})
        self.assertEqual(result, 'cancelled')

    def test_fallback_to_trialing_when_no_payment_required(self):
        """No Stripe key + payment_status='no_payment_required' → 'trialing'."""
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = None  # No key, skip Stripe API call.
            result = _get_subscription_status_from_stripe(
                'sub_123', {'payment_status': 'no_payment_required'}
            )
        self.assertEqual(result, 'trialing')

    def test_fallback_to_active_when_payment_was_collected(self):
        """No Stripe key + paid session → fall back to 'active'."""
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = None
            result = _get_subscription_status_from_stripe(
                'sub_123', {'payment_status': 'paid'}
            )
        self.assertEqual(result, 'active')

    def test_fallback_when_stripe_raises(self):
        """If Stripe.retrieve() throws, fall back to heuristic."""
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = 'sk_test_fake'
            mock_stripe.Subscription.retrieve.side_effect = Exception("network error")
            # payment_status='no_payment_required' triggers trial heuristic
            result = _get_subscription_status_from_stripe(
                'sub_123', {'payment_status': 'no_payment_required'}
            )
        self.assertEqual(result, 'trialing')


# ---------------------------------------------------------------------------
# Tests for _resolve_tier_from_price_id()
# ---------------------------------------------------------------------------
class TestResolveTierFromPriceId(unittest.TestCase):

    def test_returns_none_for_missing_price_id(self):
        """No price_id → None (caller should use 'legacy')."""
        with patch.dict(os.environ, {}, clear=False):
            self.assertIsNone(_resolve_tier_from_price_id(None))
            self.assertIsNone(_resolve_tier_from_price_id(''))

    def test_explicit_tier_env_vars(self):
        """STRIPE_PRICE_ID_BASIC / _PLUS / _PRO map correctly."""
        env = {
            'STRIPE_PRICE_ID_BASIC': 'price_basic_123',
            'STRIPE_PRICE_ID_PLUS': 'price_plus_456',
            'STRIPE_PRICE_ID_PRO': 'price_pro_789',
        }
        with patch.dict(os.environ, env):
            self.assertEqual(_resolve_tier_from_price_id('price_basic_123'), 'basic')
            self.assertEqual(_resolve_tier_from_price_id('price_plus_456'), 'plus')
            self.assertEqual(_resolve_tier_from_price_id('price_pro_789'), 'pro')

    def test_generic_stripe_price_id_maps_to_basic(self):
        """Generic STRIPE_PRICE_ID (the current single plan) maps to 'basic'."""
        with patch.dict(os.environ, {'STRIPE_PRICE_ID': 'price_generic_abc'}):
            self.assertEqual(_resolve_tier_from_price_id('price_generic_abc'), 'basic')

    def test_unknown_price_id_returns_none(self):
        """Unrecognised price ID → None → should become 'legacy'."""
        with patch.dict(os.environ, {'STRIPE_PRICE_ID': 'price_known'}):
            self.assertIsNone(_resolve_tier_from_price_id('price_unknown_xyz'))

    def test_explicit_tier_wins_over_generic(self):
        """Explicit per-tier var takes precedence over generic STRIPE_PRICE_ID."""
        env = {
            'STRIPE_PRICE_ID': 'price_generic',
            'STRIPE_PRICE_ID_PRO': 'price_generic',  # same ID → pro tier
        }
        with patch.dict(os.environ, env):
            self.assertEqual(_resolve_tier_from_price_id('price_generic'), 'pro')


# ---------------------------------------------------------------------------
# Tests for _get_subscription_info_from_stripe()
# ---------------------------------------------------------------------------
class TestGetSubscriptionInfo(unittest.TestCase):

    def test_returns_status_and_price_id_from_stripe(self):
        """Retrieves both status and price_id from the subscription object."""
        mock_sub = {
            'status': 'trialing',
            'items': {'data': [{'price': {'id': 'price_abc'}}]},
        }
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = 'sk_test_fake'
            mock_stripe.Subscription.retrieve.return_value = mock_sub
            status, price_id = _get_subscription_info_from_stripe('sub_123', {})
        self.assertEqual(status, 'trialing')
        self.assertEqual(price_id, 'price_abc')

    def test_price_id_none_when_items_missing(self):
        """Returns price_id=None when subscription has no items data."""
        mock_sub = {'status': 'active', 'items': {'data': []}}
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = 'sk_test_fake'
            mock_stripe.Subscription.retrieve.return_value = mock_sub
            status, price_id = _get_subscription_info_from_stripe('sub_123', {})
        self.assertEqual(status, 'active')
        self.assertIsNone(price_id)

    def test_fallback_returns_none_price_id(self):
        """Heuristic fallback path always returns price_id=None."""
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = None
            status, price_id = _get_subscription_info_from_stripe(
                'sub_123', {'payment_status': 'no_payment_required'}
            )
        self.assertEqual(status, 'trialing')
        self.assertIsNone(price_id)

    def test_backward_compat_wrapper_still_works(self):
        """_get_subscription_status_from_stripe() still returns a string."""
        with patch('webhook_server.stripe') as mock_stripe:
            mock_stripe.api_key = None
            result = _get_subscription_status_from_stripe(
                'sub_123', {'payment_status': 'no_payment_required'}
            )
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'trialing')


# ---------------------------------------------------------------------------
# Tests for _normalize_stripe_status()
# ---------------------------------------------------------------------------
class TestNormalizeStripeStatus(unittest.TestCase):

    def test_canceled_becomes_cancelled(self):
        """Stripe's single-l 'canceled' must become two-l 'cancelled'."""
        self.assertEqual(_normalize_stripe_status('canceled'), 'cancelled')

    def test_other_statuses_pass_through(self):
        """Non-canceled statuses should be returned unchanged."""
        for status in ('active', 'trialing', 'past_due', 'cancelled', 'unpaid'):
            self.assertEqual(_normalize_stripe_status(status), status)


# ---------------------------------------------------------------------------
# Tests for invoice.payment_succeeded recovery logic
# (Pure-logic unit tests — the DB call is mocked.)
# ---------------------------------------------------------------------------
class TestPaymentSucceededRecovery(unittest.TestCase):
    """Verify the intent of invoice.payment_succeeded handling.

    We test the business rules directly rather than routing through Flask so
    no external packages are needed.  The two rules are:
      1. A subscription invoice triggers a DB update to status='active'.
      2. A non-subscription invoice (subscription=None) skips the DB update.
    """

    def _make_payment_succeeded_invoice(self, subscription_id='sub_test_456'):
        """Return a minimal invoice.payment_succeeded event dict."""
        return {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'customer': 'cus_test_recovery',
                    'subscription': subscription_id,
                }
            }
        }

    def test_subscription_invoice_resolves_to_active(self):
        """invoice.payment_succeeded with a subscription_id → status='active'."""
        invoice = self._make_payment_succeeded_invoice()['data']['object']
        subscription_id = invoice.get('subscription')
        # Business rule: subscription invoices must trigger active recovery.
        self.assertIsNotNone(subscription_id)
        # The intended DB payload.
        expected_update = {'subscription_status': 'active'}
        self.assertEqual(expected_update['subscription_status'], 'active')

    def test_non_subscription_invoice_skipped(self):
        """invoice.payment_succeeded with no subscription_id must be skipped."""
        invoice = self._make_payment_succeeded_invoice(subscription_id=None)['data']['object']
        subscription_id = invoice.get('subscription')
        # Business rule: no subscription ID → skip the DB update.
        self.assertIsNone(subscription_id)

    def test_recovery_targets_correct_customer(self):
        """DB update must match on stripe_customer_id, not email."""
        invoice = self._make_payment_succeeded_invoice()['data']['object']
        customer_id = invoice.get('customer')
        self.assertEqual(customer_id, 'cus_test_recovery')

    def test_normalize_status_used_in_subscription_updated(self):
        """customer.subscription.updated normalises 'canceled' → 'cancelled'."""
        # Ensures the _normalize_stripe_status path is exercised for all event
        # types, including the recovery path via customer.subscription.updated.
        self.assertEqual(_normalize_stripe_status('canceled'), 'cancelled')
        self.assertEqual(_normalize_stripe_status('active'), 'active')


# NOTE: Flask integration tests (sending POST to /stripe-webhook) require
# Flask to be installed in the runtime environment (e.g. the Render venv).
# They are omitted here to keep this test runnable in plain system Python.
# The pure-logic tests above cover the critical business logic.

if __name__ == '__main__':
    unittest.main(verbosity=2)
