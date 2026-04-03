# Trial Signup Smoke Check Snapshot

Generated at: 2026-04-03T13:17:13.803643+00:00
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
- Render blueprint service contract summary: commission-tracker-app: runtime=OK, plan=OK, autoDeploy=OK, buildCommand=OK, startCommand=OK, healthCheckPath=OK; commission-tracker-webhook: runtime=OK, plan=OK, autoDeploy=OK, buildCommand=OK, startCommand=OK, healthCheckPath=OK
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
- Install the missing local webhook verification dependencies and re-run the /health import check: flask, stripe
- Load the missing Stripe, Resend, and Supabase service secrets into the verification shell before running a real checkout.

## Render restore checklist
- Open the Render dashboard for service commission-tracker-webhook.
- Confirm the service is attached to https://commission-tracker-webhook.onrender.com and not left on a stale or missing domain binding.
- Render is currently reporting x-render-routing=no-server, so prioritize service/domain attachment before reviewing Flask routes.
- Confirm the deployed start command is `gunicorn webhook_server:app --bind 0.0.0.0:${PORT}`.
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

## Local webhook dependency commands
- python3 -m pip install flask stripe
- python3 -m pip install -r requirements.txt
- python3 - <<'PY'
from webhook_server import app
client = app.test_client()
resp = client.get('/health')
print(resp.status_code)
print(resp.get_json(silent=True))
PY

## Render service env gap
- commission-tracker-app: shell_ready=NO; missing_in_shell=APP_ENVIRONMENT, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, SUPABASE_SERVICE_KEY; missing_in_blueprint=None
- commission-tracker-webhook: shell_ready=NO; missing_in_shell=APP_ENVIRONMENT, FROM_EMAIL, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, SUPABASE_SERVICE_KEY; missing_in_blueprint=None

## Render service env commands
- commission-tracker-app:
  - Render dashboard -> commission-tracker-app -> Environment: set APP_ENVIRONMENT=..., PRODUCTION_SUPABASE_ANON_KEY=..., PRODUCTION_SUPABASE_SERVICE_KEY=..., PRODUCTION_SUPABASE_URL=..., RENDER_APP_URL=..., RESEND_API_KEY=..., STRIPE_PRICE_ID=..., STRIPE_SECRET_KEY=..., SUPABASE_SERVICE_KEY=...
  - After saving env vars for commission-tracker-app, trigger a manual deploy and wait for a healthy instance.
  - Verify commission-tracker-app serves / after the deploy.
- commission-tracker-webhook:
  - Render dashboard -> commission-tracker-webhook -> Environment: set APP_ENVIRONMENT=..., FROM_EMAIL=..., PRODUCTION_SUPABASE_ANON_KEY=..., PRODUCTION_SUPABASE_SERVICE_KEY=..., PRODUCTION_SUPABASE_URL=..., RENDER_APP_URL=..., RESEND_API_KEY=..., SMTP_HOST=..., SMTP_PASS=..., SMTP_PORT=..., SMTP_USER=..., STRIPE_PRICE_ID=..., STRIPE_SECRET_KEY=..., STRIPE_WEBHOOK_SECRET=..., SUPABASE_SERVICE_KEY=...
  - After saving env vars for commission-tracker-webhook, trigger a manual deploy and wait for a healthy instance.
  - Verify commission-tracker-webhook serves /health after the deploy.

## Render service contract commands
- commission-tracker-app:
  - Render dashboard -> commission-tracker-app -> Settings: confirm runtime=python and plan=starter
  - Render dashboard -> commission-tracker-app -> Settings: confirm autoDeploy=true
  - Render dashboard -> commission-tracker-app -> Build & Deploy: confirm buildCommand='pip install -r requirements.txt'
  - Render dashboard -> commission-tracker-app -> Build & Deploy: confirm startCommand='streamlit run commission_app.py --server.port ${PORT} --server.address 0.0.0.0'
  - Render dashboard -> commission-tracker-app -> Health Check: confirm path='/'
  - Render dashboard -> commission-tracker-app -> Environment: confirm keys APP_ENVIRONMENT, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SUPABASE_URL
- commission-tracker-webhook:
  - Render dashboard -> commission-tracker-webhook -> Settings: confirm runtime=python and plan=starter
  - Render dashboard -> commission-tracker-webhook -> Settings: confirm autoDeploy=true
  - Render dashboard -> commission-tracker-webhook -> Build & Deploy: confirm buildCommand='pip install -r requirements.txt'
  - Render dashboard -> commission-tracker-webhook -> Build & Deploy: confirm startCommand='gunicorn webhook_server:app --bind 0.0.0.0:${PORT}'
  - Render dashboard -> commission-tracker-webhook -> Health Check: confirm path='/health'
  - Render dashboard -> commission-tracker-webhook -> Environment: confirm keys APP_ENVIRONMENT, FROM_EMAIL, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SUPABASE_URL

## Render domain attachment commands
- commission-tracker-app:
  - Render dashboard -> commission-tracker-app -> Settings -> Custom Domains: confirm commission-tracker-app.onrender.com is attached to this service.
  - curl -I https://commission-tracker-app.onrender.com/
  - If the app hostname is attached elsewhere or missing, reattach commission-tracker-app.onrender.com to commission-tracker-app and redeploy.
- commission-tracker-webhook:
  - Render dashboard -> commission-tracker-webhook -> Settings -> Custom Domains: confirm commission-tracker-webhook.onrender.com is attached to this service.
  - curl -I https://commission-tracker-webhook.onrender.com/health
  - If Render still returns x-render-routing=no-server, remove any stale domain attachment and reattach the webhook hostname to commission-tracker-webhook before redeploying.

## Render hostname diagnostics
- commission-tracker-app: host=commission-tracker-app.onrender.com; expected_service=commission-tracker-app; probe_path=/; attachment_state=healthy-attached; status=200 OK; x-render-origin-server=TornadoServer/6.5.5; x-render-routing=None; evidence=HTTP 200 with x-render-origin-server=TornadoServer/6.5.5
- commission-tracker-webhook: host=commission-tracker-webhook.onrender.com; expected_service=commission-tracker-webhook; probe_path=/health; attachment_state=missing-backend-attachment; status=404 Not Found; x-render-origin-server=None; x-render-routing=no-server; evidence=HTTP 404 with x-render-routing=no-server

## Render incident signature
- Repo contract OK: YES
- App host attachment state: healthy-attached
- Webhook host attachment state: missing-backend-attachment
- External routing issue isolated: YES
- Conclusion: Repo-side checkout, webhook, and Render blueprint contracts are green while the app hostname is healthy-attached and the webhook hostname is missing-backend-attachment. This points to an external Render service or domain binding problem, not an app-code route regression.

## Probe previews
- Webhook health preview: Not Found

- Webhook root preview: Not Found

