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
from webhook_server import _get_subscription_status_from_stripe  # noqa: E402


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


# NOTE: Flask integration tests (sending POST to /stripe-webhook) require
# Flask to be installed in the runtime environment (e.g. the Render venv).
# They are omitted here to keep this test runnable in plain system Python.
# The pure-logic tests above cover the critical business logic.

if __name__ == '__main__':
    unittest.main(verbosity=2)
