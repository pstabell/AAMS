# Trial Signup Smoke Check Snapshot

Generated at: 2026-04-02T19:17:23.036963+00:00
Ready for live e2e: NO

## Public checks
- App URL: https://commission-tracker-app.onrender.com -> 200 OK
- Webhook health: https://commission-tracker-webhook.onrender.com/health -> 404 Not Found
- Webhook root: https://commission-tracker-webhook.onrender.com/ -> 404 Not Found
- Webhook Render routing modes: no-server
- Webhook no-server detected: YES
- Any webhook endpoint OK: NO
- All probed webhook endpoints 404: YES
- Likely webhook cause: Render is reporting x-render-routing=no-server for the webhook hostname. That usually means there is no healthy backend service attached to this route yet or the service is not deployed behind the expected domain.

## Local checks
- Local webhook route OK: NO
- Local webhook payload: Local Python dependencies missing for webhook import
- Checkout contract OK: YES
- Checkout contract payload: {'mode': 'subscription', 'trial_period_days': 14, 'payment_method_collection': 'if_required', 'allow_promotion_codes': True, 'success_url': 'https://commission-tracker-app.onrender.com/?session_id={CHECKOUT_SESSION_ID}', 'cancel_url': 'https://commission-tracker-app.onrender.com', 'metadata_keys': ['accepted_at', 'accepted_privacy', 'accepted_terms', 'privacy_version', 'terms_version']}
- Render blueprint OK: YES
- Render blueprint payload: Render blueprint looks complete
- Webhook service contract OK: YES
- Webhook service contract payload: Webhook service contract looks complete

## Missing required env vars
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_ID
- RESEND_API_KEY
- SUPABASE_SERVICE_KEY

## Blocking reasons
- Public webhook health URL https://commission-tracker-webhook.onrender.com/health is not healthy: 404 Not Found
- Render is reporting x-render-routing=no-server for the webhook hostname. That usually means there is no healthy backend service attached to this route yet or the service is not deployed behind the expected domain.
- Local webhook /health verification failed in this workspace.
- Required live E2E secrets are missing from this shell: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY

## Recommended next actions
- Render is signaling no-server for the webhook hostname; reattach or redeploy the webhook backend behind the expected domain.
- Fix the local webhook import/runtime issue before trusting deployment parity.
- Load the missing Stripe, Resend, and Supabase service secrets into the verification shell before running a real checkout.

## Render restore checklist
- Open the Render dashboard for service commission-tracker-webhook.
- Confirm the service is attached to https://commission-tracker-webhook.onrender.com and not left on a stale or missing domain binding.
- Render is currently reporting x-render-routing=no-server, so prioritize service/domain attachment before reviewing Flask routes.
- Confirm the deployed start command is `gunicorn webhook_server:app`.
- Confirm the health check path is `/health`.
- Trigger a manual deploy or blueprint sync if the service is missing, suspended, or attached to the wrong branch.
- Watch deploy logs until the service reports a healthy instance and the custom onrender.com hostname is bound.
- Re-run python3 scripts/trial_signup_smoke_check.py against https://commission-tracker-webhook.onrender.com and confirm /health no longer returns x-render-routing=no-server.
- After routing is restored, load the missing live secrets in the verification shell before running a real Stripe test signup: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- When the smoke check turns green, run one real Stripe test-mode signup and capture the session ID, webhook timestamp, and onboarding email evidence.

## Render restore validation commands
- curl -i https://commission-tracker-webhook.onrender.com/health
- python3 scripts/trial_signup_smoke_check.py
- export STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=... STRIPE_PRICE_ID=... RESEND_API_KEY=... SUPABASE_SERVICE_KEY=...
- python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md
- python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py

## Probe previews
- Webhook health preview: Not Found

- Webhook root preview: Not Found

