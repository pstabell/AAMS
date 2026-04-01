# Trial Signup End-to-End Test Report

**Date:** 2026-04-01
**Tester:** Forge
**Repo:** AMS-APP
**Card:** Activation Engine: End-to-End Trial Signup Test

## Scope
Validate the solo-agent trial signup path from signup form through Stripe checkout configuration, account provisioning webhook behavior, and onboarding email path.

## What Was Verified

### 1. Automated checkout and webhook regression suite
Command run:

```bash
python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py
```

Result:
- 147 tests ran
- 147 tests passed

Coverage confirmed by the existing regression suite includes:
- Terms of Service and Privacy Policy acceptance required before checkout
- Stripe checkout session built in subscription mode
- 14-day free trial applied
- `payment_method_collection='if_required'`
- Legal-acceptance metadata attached to checkout
- Success-page resend-setup flow
- Expired setup-token resend flow
- Subscription status normalization and webhook fallback logic
- Tier resolution from Stripe price IDs
- Payment recovery webhook logic

### 2. Checkout session contract
Confirmed from live code in `auth_helpers.py` and direct invocation of `_build_checkout_kwargs(...)`:
- mode: `subscription`
- trial period: `14` days
- payment method collection: `if_required`
- promotion codes enabled: `True`
- success URL: `https://commission-tracker-app.onrender.com/?session_id={CHECKOUT_SESSION_ID}`
- cancel URL: `https://commission-tracker-app.onrender.com`
- metadata includes:
  - accepted_terms=true
  - accepted_privacy=true
  - accepted_at timestamp
  - terms_version=2024-12-06
  - privacy_version=2024-12-06

### 3. Live app reachability
Checked:
- `https://commission-tracker-app.onrender.com`

Result:
- Main Streamlit app is reachable and returns HTTP 200.

## Blockers / Breaks Found

### 1. Live webhook endpoint is not reachable at the documented URL
Checked:
- `https://commission-tracker-webhook.onrender.com/health`

Result:
- Returns HTTP 404 `Not Found`

Impact:
- I could not verify the deployed provisioning webhook health endpoint.
- A real Stripe checkout cannot be trusted to provision an account and trigger onboarding email until the live webhook service is reachable.

### 2. Local workspace does not have the secrets needed for a real external end-to-end purchase test
Missing in the current shell:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`
- `RESEND_API_KEY`
- `APP_URL`
- `APP_PASSWORD`
- `SUPABASE_SERVICE_KEY`

Available:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

Impact:
- I could validate code paths and regression coverage locally.
- I could not execute a true paid external Stripe checkout from this workspace with live billing, live webhook signature validation, and live onboarding email delivery.

## Assessment
The codebase appears healthy for the trial signup flow based on the current regression suite and direct inspection of checkout and webhook logic. The active risk is deployment/runtime, not the core Python logic.

The most important production issue found is that the documented webhook health URL currently returns 404. That blocks a trustworthy real-world confirmation of account provisioning and onboarding email delivery.

## Recommended Next Actions
1. Restore or verify the live Render webhook service at `commission-tracker-webhook.onrender.com`.
2. Apply the checked-in `render.yaml` blueprint so Render explicitly uses `gunicorn webhook_server:app` with `healthCheckPath: /health` for the webhook service and the Streamlit start command for the main app.
3. After the webhook health endpoint is reachable, run one real Stripe test-mode trial signup using a test card or no-card-required trial path.
4. Confirm in production logs that:
   - `checkout.session.completed` is received
   - user row is created or updated in `users`
   - setup token is inserted into `password_reset_tokens`
   - password setup email is sent successfully
5. Capture the subscriber email, Stripe session ID, and webhook log timestamp in a follow-up report.

## Conclusion
Status: **Blocked for full live end-to-end confirmation**

Reason:
- Live webhook health endpoint returns 404
- Required live Stripe/email secrets are not available in the current workspace session

Automated coverage status: **Pass**
Deployment/runtime validation status: **Blocked pending webhook restoration**
