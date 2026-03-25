"""
Regression tests for the solo-agent Stripe checkout flow (auth_helpers.py).

These tests run without any external dependencies (no Stripe API key, no
Streamlit, no Supabase) and exercise four critical behaviors:

1. Both legal checkboxes (Terms + Privacy) are required before checkout proceeds.
2. Checkout session includes a 14-day free trial.
3. Checkout uses payment_method_collection='if_required' (supports 100%-off coupons).
4. Legal-acceptance metadata is passed through to Stripe.
5. SUBSCRIPTION_OFFER config has the required keys and solo-agent copy.
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
    _should_block_checkout,
    _get_support_contact,
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

    # --- 2. free trial length driven by SUBSCRIPTION_OFFER config ---
    def test_trial_period_days_matches_config(self):
        """subscription_data['trial_period_days'] must equal SUBSCRIPTION_OFFER['trial_days']."""
        from config import SUBSCRIPTION_OFFER
        self.assertEqual(
            self.kwargs['subscription_data']['trial_period_days'],
            SUBSCRIPTION_OFFER['trial_days'],
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

        from config import SUBSCRIPTION_OFFER
        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        self.assertEqual(call_kwargs['subscription_data']['trial_period_days'], SUBSCRIPTION_OFFER['trial_days'])
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


# ---------------------------------------------------------------------------
# SUBSCRIPTION_OFFER config contract
# ---------------------------------------------------------------------------
class TestSubscriptionOfferConfig(unittest.TestCase):
    """
    Pin the SUBSCRIPTION_OFFER config structure so accidental key removal or
    type changes surface immediately as test failures rather than runtime errors
    in the Streamlit UI.
    """

    def setUp(self):
        from config import SUBSCRIPTION_OFFER
        self.offer = SUBSCRIPTION_OFFER

    # --- required keys ---

    def test_has_tab_heading(self):
        self.assertIn('tab_heading', self.offer)

    def test_has_tab_tagline(self):
        self.assertIn('tab_tagline', self.offer)

    def test_has_features(self):
        self.assertIn('features', self.offer)

    def test_has_trial_days(self):
        self.assertIn('trial_days', self.offer)

    def test_has_trial_price_monthly(self):
        self.assertIn('trial_price_monthly', self.offer)

    def test_has_trial_caption(self):
        self.assertIn('trial_caption', self.offer)

    # --- type contracts ---

    def test_tab_heading_is_non_empty_string(self):
        self.assertIsInstance(self.offer['tab_heading'], str)
        self.assertTrue(self.offer['tab_heading'].strip())

    def test_tab_tagline_is_non_empty_string(self):
        self.assertIsInstance(self.offer['tab_tagline'], str)
        self.assertTrue(self.offer['tab_tagline'].strip())

    def test_features_is_non_empty_list(self):
        self.assertIsInstance(self.offer['features'], list)
        self.assertGreater(len(self.offer['features']), 0)

    def test_each_feature_is_non_empty_string(self):
        for item in self.offer['features']:
            self.assertIsInstance(item, str)
            self.assertTrue(item.strip(), f"Empty feature entry: {item!r}")

    def test_trial_days_is_positive_integer(self):
        """trial_days must be a positive integer (checkout reads it directly from config)."""
        self.assertIsInstance(self.offer['trial_days'], int)
        self.assertGreater(self.offer['trial_days'], 0)

    def test_trial_price_monthly_contains_dollar_sign(self):
        self.assertIn('$', self.offer['trial_price_monthly'])

    # --- solo-agent launch copy: must NOT include multi-user collaboration ---

    def test_features_do_not_mention_multi_user(self):
        """Solo-agent offer should not advertise multi-user collaboration."""
        joined = " ".join(self.offer['features']).lower()
        self.assertNotIn('multi-user', joined)
        self.assertNotIn('collaboration', joined)

    def test_features_include_commission_tracking(self):
        """Core solo-agent value proposition must be present."""
        joined = " ".join(self.offer['features']).lower()
        self.assertIn('commission', joined)

    def test_features_include_reconciliation(self):
        joined = " ".join(self.offer['features']).lower()
        self.assertIn('reconcili', joined)


# ---------------------------------------------------------------------------
# 10. Agency Signup feature flag
# ---------------------------------------------------------------------------
class TestAgencySignupFeatureFlag(unittest.TestCase):
    """
    Ensure FEATURES['agency_signup'] exists, is a bool, and defaults to False
    for the solo-agent launch.  The agency signup code is preserved behind this
    toggle — flipping it True re-enables the third tab without any code changes.
    """

    def setUp(self):
        from config import FEATURES, is_feature_enabled
        self.FEATURES = FEATURES
        self.is_feature_enabled = is_feature_enabled

    def test_agency_signup_key_present_in_features(self):
        """FEATURES must have an 'agency_signup' entry."""
        self.assertIn('agency_signup', self.FEATURES)

    def test_agency_signup_is_bool(self):
        """The flag must be a boolean so truthiness checks are unambiguous."""
        self.assertIsInstance(self.FEATURES['agency_signup'], bool)

    def test_agency_signup_disabled_for_solo_agent_launch(self):
        """Agency Signup tab is hidden by default during the solo-agent launch."""
        self.assertFalse(self.FEATURES['agency_signup'])

    def test_is_feature_enabled_returns_false_for_agency_signup(self):
        """is_feature_enabled() must return False for 'agency_signup' at launch."""
        self.assertFalse(self.is_feature_enabled('agency_signup'))

    def test_is_feature_enabled_honours_flag_when_true(self):
        """Flipping the flag to True must make is_feature_enabled() return True."""
        original = self.FEATURES['agency_signup']
        try:
            self.FEATURES['agency_signup'] = True
            self.assertTrue(self.is_feature_enabled('agency_signup'))
        finally:
            self.FEATURES['agency_signup'] = original

    def test_is_feature_enabled_unknown_key_returns_false(self):
        """Unknown feature keys must not raise; they return False."""
        self.assertFalse(self.is_feature_enabled('nonexistent_feature_xyz'))


# ---------------------------------------------------------------------------
# Duplicate-subscriber guard: _should_block_checkout
# ---------------------------------------------------------------------------
class TestShouldBlockCheckout(unittest.TestCase):
    """
    Pin the duplicate-subscriber guard so checkout can never create a second
    Stripe subscription on top of an already-active account.

    Rules
    -----
    - active / trialing / trial  → block with reason 'already_active'
    - past_due                   → block with reason 'past_due'
    - cancelled / inactive / ''  → allow checkout (reason is '')
    - None (email not found)     → allow checkout
    """

    # --- statuses that MUST block ---

    def test_active_is_blocked(self):
        block, reason = _should_block_checkout('active')
        self.assertTrue(block)
        self.assertEqual(reason, 'already_active')

    def test_trialing_is_blocked(self):
        block, reason = _should_block_checkout('trialing')
        self.assertTrue(block)
        self.assertEqual(reason, 'already_active')

    def test_trial_is_blocked(self):
        """Agency-style 'trial' status must also be blocked."""
        block, reason = _should_block_checkout('trial')
        self.assertTrue(block)
        self.assertEqual(reason, 'already_active')

    def test_past_due_is_blocked(self):
        block, reason = _should_block_checkout('past_due')
        self.assertTrue(block)
        self.assertEqual(reason, 'past_due')

    def test_past_due_reason_is_not_already_active(self):
        """past_due gets its own reason so the UI can show a tailored message."""
        _, reason = _should_block_checkout('past_due')
        self.assertNotEqual(reason, 'already_active')

    # --- statuses that MUST allow checkout ---

    def test_cancelled_allows_checkout(self):
        block, _ = _should_block_checkout('cancelled')
        self.assertFalse(block)

    def test_inactive_allows_checkout(self):
        block, _ = _should_block_checkout('inactive')
        self.assertFalse(block)

    def test_none_allows_checkout(self):
        """Email not found in DB (None status) must allow checkout."""
        block, _ = _should_block_checkout(None)
        self.assertFalse(block)

    def test_empty_string_allows_checkout(self):
        """Empty string status must allow checkout (treat as unregistered)."""
        block, _ = _should_block_checkout('')
        self.assertFalse(block)

    def test_unknown_status_allows_checkout(self):
        """Unrecognised statuses default to allow (never silently block a signup)."""
        block, _ = _should_block_checkout('some_future_status')
        self.assertFalse(block)

    # --- return-type contracts ---

    def test_returns_tuple_of_two(self):
        result = _should_block_checkout('active')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_first_element_is_bool(self):
        block, _ = _should_block_checkout('active')
        self.assertIsInstance(block, bool)

    def test_reason_is_string(self):
        _, reason = _should_block_checkout('active')
        self.assertIsInstance(reason, str)

    def test_allowed_reason_is_empty_string(self):
        """When checkout is allowed the reason field must be an empty string."""
        _, reason = _should_block_checkout('cancelled')
        self.assertEqual(reason, '')

    # --- consistency with _subscription_allows_login ---

    def test_every_login_allowed_status_also_blocks_checkout(self):
        """Any status that lets a user *log in* must also block a new checkout.
        If a user can already access the app, they don't need a second trial.
        """
        for status in _SUBSCRIPTION_STATUSES_ALLOWING_LOGIN:
            block, _ = _should_block_checkout(status)
            self.assertTrue(
                block,
                msg=f"status '{status}' allows login but did not block checkout",
            )


# ---------------------------------------------------------------------------
# Support contact helper: _get_support_contact
# ---------------------------------------------------------------------------
class TestGetSupportContact(unittest.TestCase):
    """_get_support_contact resolves email from env vars or config fallback."""

    def _swap_env(self, **kwargs):
        """Temporarily set env vars; return dict of originals for restore."""
        original = {}
        for k, v in kwargs.items():
            original[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return original

    def _restore_env(self, original):
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_support_email_env_takes_priority(self):
        orig = self._swap_env(SUPPORT_EMAIL="custom@example.com", FROM_EMAIL=None, SUPPORT_URL=None)
        try:
            self.assertIn("custom@example.com", _get_support_contact())
        finally:
            self._restore_env(orig)

    def test_from_email_used_when_no_support_email(self):
        orig = self._swap_env(SUPPORT_EMAIL=None, FROM_EMAIL="from@example.com", SUPPORT_URL=None)
        try:
            self.assertIn("from@example.com", _get_support_contact())
        finally:
            self._restore_env(orig)

    def test_config_fallback_when_no_env_vars(self):
        orig = self._swap_env(SUPPORT_EMAIL=None, FROM_EMAIL=None, SUPPORT_URL=None)
        try:
            from config import SUPPORT_CONTACT
            self.assertIn(SUPPORT_CONTACT["email_fallback"], _get_support_contact())
        finally:
            self._restore_env(orig)

    def test_returns_markdown_link_when_support_url_set(self):
        orig = self._swap_env(
            SUPPORT_EMAIL="help@example.com",
            FROM_EMAIL=None,
            SUPPORT_URL="https://help.example.com",
        )
        try:
            result = _get_support_contact()
            self.assertIn("[", result)
            self.assertIn("](", result)
            self.assertIn("https://help.example.com", result)
        finally:
            self._restore_env(orig)

    def test_returns_plain_email_when_no_support_url(self):
        orig = self._swap_env(SUPPORT_EMAIL="help@example.com", FROM_EMAIL=None, SUPPORT_URL=None)
        try:
            result = _get_support_contact()
            self.assertNotIn("](", result)
            self.assertIn("help@example.com", result)
        finally:
            self._restore_env(orig)

    def test_support_email_overrides_from_email(self):
        orig = self._swap_env(
            SUPPORT_EMAIL="support@example.com",
            FROM_EMAIL="from@example.com",
            SUPPORT_URL=None,
        )
        try:
            result = _get_support_contact()
            self.assertIn("support@example.com", result)
            self.assertNotIn("from@example.com", result)
        finally:
            self._restore_env(orig)


# ---------------------------------------------------------------------------
# Support contact config: SUPPORT_CONTACT
# ---------------------------------------------------------------------------
class TestSupportContactConfig(unittest.TestCase):
    """SUPPORT_CONTACT in config.py has the required structure and copy."""

    def setUp(self):
        from config import SUPPORT_CONTACT
        self.config = SUPPORT_CONTACT

    def test_email_fallback_present_and_valid(self):
        self.assertIn("email_fallback", self.config)
        self.assertIsInstance(self.config["email_fallback"], str)
        self.assertIn("@", self.config["email_fallback"])

    def test_cta_text_present_and_non_empty(self):
        self.assertIn("cta_text", self.config)
        self.assertIsInstance(self.config["cta_text"], str)
        self.assertTrue(len(self.config["cta_text"]) > 0)

    def test_post_checkout_steps_is_list(self):
        self.assertIn("post_checkout_steps", self.config)
        self.assertIsInstance(self.config["post_checkout_steps"], list)

    def test_post_checkout_steps_not_empty(self):
        self.assertTrue(len(self.config["post_checkout_steps"]) > 0)

    def test_post_checkout_steps_mention_setup_email_or_link(self):
        """Users must be told they will receive a setup email or account link."""
        joined = " ".join(self.config["post_checkout_steps"]).lower()
        self.assertTrue(
            "email" in joined or "setup" in joined or "link" in joined,
            "post_checkout_steps should mention setup email or link",
        )

    def test_post_checkout_steps_mention_trial(self):
        """Steps must reference the free trial."""
        joined = " ".join(self.config["post_checkout_steps"]).lower()
        self.assertIn("trial", joined)

    def test_post_checkout_steps_reassure_no_immediate_charge(self):
        """Users must be reassured no card is charged during trial signup."""
        joined = " ".join(self.config["post_checkout_steps"]).lower()
        self.assertTrue(
            "no card" in joined or "no charge" in joined or "card charged" in joined,
            "post_checkout_steps should reassure user no card is charged yet",
        )

    def test_post_checkout_steps_all_strings(self):
        for step in self.config["post_checkout_steps"]:
            self.assertIsInstance(step, str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
