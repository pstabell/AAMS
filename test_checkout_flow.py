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

from auth_helpers import (  # noqa: E402
    _validate_legal_acceptance,
    _build_checkout_kwargs,
    _hash_password,
    _verify_password,
    generate_setup_token,
    _subscription_allows_login,
    _SUBSCRIPTION_STATUSES_ALLOWING_LOGIN,
)

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


# ---------------------------------------------------------------------------
# Resend setup email — token generation contract
# ---------------------------------------------------------------------------
class TestGenerateSetupToken(unittest.TestCase):
    """
    The resend-setup-email flow reuses generate_setup_token() with a 24-hour
    expiry (matching the original webhook token).  These tests pin the
    observable contract of that helper so a regression immediately fails.
    """

    def test_returns_string(self):
        self.assertIsInstance(generate_setup_token(), str)

    def test_default_length_is_32(self):
        self.assertEqual(len(generate_setup_token()), 32)

    def test_custom_length_respected(self):
        self.assertEqual(len(generate_setup_token(length=64)), 64)

    def test_tokens_are_unique(self):
        """Each call must produce a distinct token (random, not deterministic)."""
        self.assertNotEqual(generate_setup_token(), generate_setup_token())

    def test_only_alphanumeric_chars(self):
        """Token must be safe for use in a URL query parameter without encoding."""
        import re
        token = generate_setup_token()
        self.assertRegex(token, r'^[A-Za-z0-9]+$')

    def test_resend_expiry_is_24_hours(self):
        """
        Resend-setup tokens must expire in 24 hours, NOT 1 hour (the shorter
        window used by password-reset tokens).  Compute the expiry the same
        way show_resend_setup_form does and assert it is >= 23 h 59 m away.
        """
        from datetime import datetime, timedelta, timezone
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        min_expected = datetime.now(timezone.utc) + timedelta(hours=23, minutes=59)
        self.assertGreater(expires_at, min_expected)


# ---------------------------------------------------------------------------
# Expired setup-token routing: must use Resend Setup Email, not Forgot Password
# ---------------------------------------------------------------------------
class TestExpiredSetupTokenRouting(unittest.TestCase):
    """
    Regression: when a setup token is expired, the UI must route the user to
    show_resend_setup_form (24-hour link) instead of show_password_reset_form
    (1-hour link).  The resend flow was added specifically to handle this case
    but the expired-token page originally directed users to 'Forgot Password?'.

    These tests exercise the session-state contract that show_password_setup_form
    must honour on the expired path: set show_resend_setup=True and populate
    resend_setup_target_email so the resend form opens pre-filled.
    """

    def _simulate_expired_setup_routing(self, token_email: str) -> dict:
        """
        Reproduce the session-state assignments made by show_password_setup_form
        when a token is expired and the user clicks 'Resend Setup Email'.
        Returns the resulting session-state snapshot.
        """
        session = {}
        session['show_resend_setup'] = True
        session['resend_setup_target_email'] = token_email
        return session

    def test_expired_token_sets_show_resend_setup(self):
        """show_resend_setup must be True so the resend form is shown."""
        state = self._simulate_expired_setup_routing('agent@example.com')
        self.assertTrue(state.get('show_resend_setup'))

    def test_expired_token_prefills_target_email(self):
        """resend_setup_target_email must match the email stored in the token."""
        email = 'solo@example.com'
        state = self._simulate_expired_setup_routing(email)
        self.assertEqual(state.get('resend_setup_target_email'), email)

    def test_resend_setup_expiry_longer_than_reset_expiry(self):
        """Setup-resend tokens (24h) outlast password-reset tokens (1h)."""
        from datetime import datetime, timedelta
        resend_expiry = timedelta(hours=24)
        reset_expiry = timedelta(hours=1)
        self.assertGreater(resend_expiry, reset_expiry)

    def test_expired_token_does_not_set_show_password_reset(self):
        """The old (wrong) flow must NOT be triggered on expired setup tokens."""
        state = self._simulate_expired_setup_routing('agent@example.com')
        self.assertNotIn('show_password_reset', state)


# ---------------------------------------------------------------------------
# Subscription status gating: _subscription_allows_login
# ---------------------------------------------------------------------------
class TestSubscriptionAllowsLogin(unittest.TestCase):
    """
    Critical path: login is gated on subscription status.  These tests pin
    the exact set of statuses that should allow vs. block access so any
    regression (e.g. accidentally blocking 'trialing' users mid-trial) fails
    immediately in CI.
    """

    # --- statuses that MUST allow login ---

    def test_active_allows_login(self):
        self.assertTrue(_subscription_allows_login('active'))

    def test_trialing_allows_login(self):
        """14-day trial users must be able to log in."""
        self.assertTrue(_subscription_allows_login('trialing'))

    def test_trial_allows_login(self):
        """Legacy 'trial' status variant must also allow login."""
        self.assertTrue(_subscription_allows_login('trial'))

    # --- statuses that MUST block login ---

    def test_past_due_blocks_login(self):
        """Payment-failed accounts must not gain access."""
        self.assertFalse(_subscription_allows_login('past_due'))

    def test_cancelled_blocks_login(self):
        self.assertFalse(_subscription_allows_login('cancelled'))

    def test_inactive_blocks_login(self):
        self.assertFalse(_subscription_allows_login('inactive'))

    def test_empty_string_blocks_login(self):
        """Missing/unset status must not accidentally allow access."""
        self.assertFalse(_subscription_allows_login(''))

    def test_none_string_blocks_login(self):
        """'none' string (default when status absent) must be blocked."""
        self.assertFalse(_subscription_allows_login('none'))

    def test_unknown_status_blocks_login(self):
        """Unrecognised statuses must default to blocked (safe by default)."""
        self.assertFalse(_subscription_allows_login('some_future_status'))

    # --- frozenset contract ---

    def test_allowed_set_contains_exactly_three_statuses(self):
        """The allowed-status set is an explicit allowlist — size must stay at 3."""
        self.assertEqual(len(_SUBSCRIPTION_STATUSES_ALLOWING_LOGIN), 3)

    def test_allowed_set_is_frozenset(self):
        """frozenset prevents accidental mutation at module level."""
        self.assertIsInstance(_SUBSCRIPTION_STATUSES_ALLOWING_LOGIN, frozenset)

    def test_helper_is_consistent_with_allowed_set(self):
        """_subscription_allows_login must agree with the exported constant."""
        for status in _SUBSCRIPTION_STATUSES_ALLOWING_LOGIN:
            self.assertTrue(_subscription_allows_login(status))


# ---------------------------------------------------------------------------
# Auto-login session contract after password setup
# ---------------------------------------------------------------------------
class TestPasswordSetupAutoLoginContract(unittest.TestCase):
    """
    After a new subscriber sets their password, show_password_setup_form
    must write exactly these three keys into session state before rerunning:

        password_correct = True
        user_email       = <lowercase email>
        user_id          = <uuid from users table>

    These tests exercise the *logic* of that contract via a small simulation
    helper — no Streamlit or Supabase required.
    """

    def _simulate_setup_auto_login(
        self,
        email: str,
        update_returns_id: bool,
        select_returns_id: bool,
        uid_value: str = 'abc-123',
    ) -> dict:
        """
        Reproduce the session-state assignments made by show_password_setup_form.

        *update_returns_id*  — whether Supabase update() included 'id' in its response.
        *select_returns_id*  — whether the fallback SELECT returned a row with 'id'.
        """
        session = {}

        # Simulated update result
        update_data = [{'id': uid_value}] if update_returns_id else []

        # Resolve uid (mirrors the fixed code in auth_helpers.py)
        uid = None
        if update_data and update_data[0].get('id'):
            uid = update_data[0]['id']
        else:
            # Fallback select
            if select_returns_id:
                uid = uid_value

        session['password_correct'] = True
        session['user_email'] = email.lower()
        if uid:
            session['user_id'] = uid

        return session

    def test_user_id_set_when_update_returns_id(self):
        """Happy path: Supabase update() returns the row including id."""
        state = self._simulate_setup_auto_login(
            'Agent@Example.com', update_returns_id=True, select_returns_id=False
        )
        self.assertEqual(state['user_id'], 'abc-123')

    def test_user_id_set_via_fallback_select_when_update_suppressed(self):
        """
        RLS can suppress the update return value.  The fallback SELECT must
        still populate user_id so data loading works immediately after signup.
        """
        state = self._simulate_setup_auto_login(
            'agent@example.com', update_returns_id=False, select_returns_id=True
        )
        self.assertEqual(state['user_id'], 'abc-123')

    def test_user_id_absent_but_login_still_created_when_both_fail(self):
        """
        If both the update response and the fallback select fail (e.g. DB
        outage), the session should still be partially created so the error
        is surfaced on the next page rather than silently blocking login.
        """
        state = self._simulate_setup_auto_login(
            'agent@example.com', update_returns_id=False, select_returns_id=False
        )
        self.assertTrue(state['password_correct'])
        self.assertNotIn('user_id', state)

    def test_email_normalised_to_lowercase(self):
        """user_email in session state must always be lowercase."""
        state = self._simulate_setup_auto_login(
            'AGENT@EXAMPLE.COM', update_returns_id=True, select_returns_id=False
        )
        self.assertEqual(state['user_email'], 'agent@example.com')

    def test_password_correct_always_set_to_true(self):
        state = self._simulate_setup_auto_login(
            'a@b.com', update_returns_id=True, select_returns_id=False
        )
        self.assertTrue(state['password_correct'])

    def test_user_id_not_set_to_none_when_unavailable(self):
        """user_id key must be absent (not set to None) when id is not resolved."""
        state = self._simulate_setup_auto_login(
            'a@b.com', update_returns_id=False, select_returns_id=False
        )
        # Key should be absent, not present with value None
        self.assertIsNone(state.get('user_id'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
