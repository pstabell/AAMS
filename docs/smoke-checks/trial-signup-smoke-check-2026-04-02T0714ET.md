# Trial Signup Smoke Check Snapshot

Generated at: 2026-04-02T11:18:30.832483+00:00
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

## Probe previews
- Webhook health preview: Not Found

- Webhook root preview: Not Found

