# Trial Signup End-to-End Test Report

**Date:** 2026-04-01
**Tester:** Forge
**Repo:** AMS-APP
**Card:** Activation Engine: End-to-End Trial Signup Test

## Scope
Validate the solo-agent trial signup path from signup form through Stripe checkout configuration, account provisioning webhook behavior, and onboarding email path.

## Latest Update
- 2026-04-03 11:16 PM ET: Added an `unchanged_blocked_streak` counter to `scripts/trial_signup_smoke_check.py` and refreshed `docs/smoke-checks/latest-trial-signup-smoke-check.json` and `.md`.
- The smoke-check summary now reports how many consecutive blocked runs have produced no material recovery, so Traction can see at a glance whether the Render outage is still frozen or actually changing between handoffs.
- Fresh live evidence still isolates the outage to external Render routing and domain binding, not repo-side code drift: `commission-tracker-app.onrender.com` returns HTTP 200 with `x-render-origin-server: TornadoServer/6.5.5`, while every probed webhook path still returns HTTP 404 with `x-render-routing: no-server`.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 180/180.

## What Was Verified

### 1. Automated checkout and webhook regression suite
Command run:

```bash
python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py
```

Result:
- 152 tests ran
- 152 tests passed

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
- Smoke-check readiness gate behavior for green and blocked deployment states via `test_trial_signup_smoke_check.py`

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

### 1. Live webhook service appears misconfigured at the public Render URL
Checked:
- `https://commission-tracker-webhook.onrender.com/`
- `https://commission-tracker-webhook.onrender.com/health`
- `https://commission-tracker-webhook.onrender.com/test`
- `https://commission-tracker-webhook.onrender.com/stripe-webhook`

Result:
- All four probed endpoints return HTTP 404 `Not Found`
- Every probed webhook response also includes the header `x-render-routing: no-server`

Impact:
- This is stronger evidence than a single missing `/health` route.
- The live hostname is not just missing one endpoint; Render is explicitly signaling that no healthy backend server is attached to that route.
- The likely issue is Render service wiring, missing deployment attachment to the custom hostname, or a webhook service that is not currently standing up behind `commission-tracker-webhook.onrender.com`.
- A real Stripe checkout cannot be trusted to provision an account and trigger onboarding email until the live webhook service is restored at the expected public URL.

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
2. Apply the checked-in `render.yaml` blueprint so Render explicitly uses `gunicorn webhook_server:app --bind 0.0.0.0:${PORT}` with `healthCheckPath: /health` for the webhook service and the Streamlit start command for the main app.
3. Run `python3 scripts/trial_signup_smoke_check.py` before and after the Render change to capture a consistent readiness snapshot for the public app URL, public webhook health URL, local `/health` route, and required live E2E environment variables.
4. After the webhook health endpoint is reachable, run one real Stripe test-mode trial signup using a test card or no-card-required trial path.
5. Confirm in production logs that:
   - `checkout.session.completed` is received
   - user row is created or updated in `users`
   - setup token is inserted into `password_reset_tokens`
   - password setup email is sent successfully
6. Capture the subscriber email, Stripe session ID, and webhook log timestamp in a follow-up report.

## Follow-up Automation Added
A lightweight smoke-check helper now lives at `scripts/trial_signup_smoke_check.py`.

It reports:
- Public app reachability
- Public webhook health reachability
- Multi-endpoint webhook diagnostics across `/`, `/health`, `/test`, and `/stripe-webhook`
- Local Flask `/health` route status from `webhook_server.py`
- Presence of the core env vars needed for a true live end-to-end trial test

The script exits non-zero until the stack is genuinely ready for a live signup test, so it can also be reused in CI or a deployment shell as a fast gate.

It now also supports `--json-out` and `--markdown-out` so each run can leave behind a machine-readable snapshot plus a clean handoff note for operations after a Render change.

It now captures key response headers as part of the diagnostic snapshot, including Render routing fingerprints like `x-render-routing` and origin-server hints when present. That makes it easier to distinguish app-code failures from infrastructure states such as Render returning `no-server` before the request ever reaches Flask.

It now also emits explicit `blocking_reasons` and `next_actions` in both JSON and Markdown output so operations gets a ready-to-forward remediation list instead of having to infer the next move from raw probe data.

It now also statically verifies the checked-in Stripe checkout contract in `auth_helpers.py` without needing Streamlit to import locally, so each smoke-check run confirms the solo-agent flow still uses subscription mode, a 14-day trial, `payment_method_collection='if_required'`, promotion codes enabled, the expected success and cancel URLs, and the legal-acceptance metadata keys.

It now also verifies the checked-in `render.yaml` blueprint itself, confirming both Render services are declared with the expected start commands, health check paths, and required environment variable keys. That separates repo-side deploy configuration drift from the still-live external Render routing failure.

It now also emits a targeted `render_restore_checklist` in both JSON and Markdown output. That checklist names the exact Render service, expected hostname, checked-in start command, health check path, and the follow-up verification step so ops can restore the webhook runtime without reverse-engineering the repo first.

It now also emits `render_restore_validation_commands` in both JSON and Markdown output. That gives ops a copy-paste validation sequence covering the public webhook probe, smoke-check rerun, secret loading, artifact refresh, and regression suite after the Render service is restored.

It now also emits `local_webhook_dependency_commands` in both JSON and Markdown output so anyone verifying parity locally gets exact install and recheck commands when Flask or Stripe are missing from the shell.

## Latest refresh
- Added a Render hostname diagnostics matrix to the smoke-check summary so ops can see, in one section, which public hostname is healthy and which one is missing a backend attachment.
- Updated `scripts/trial_signup_smoke_check.py` and `test_trial_signup_smoke_check.py` so the JSON and Markdown artifacts now include `render_hostname_diagnostics` alongside the existing domain-attachment, env-gap, and service-contract handoff sections.
- Fresh evidence now explicitly classifies `commission-tracker-app.onrender.com` as `healthy-attached` with `x-render-origin-server=TornadoServer/6.5.5`, while `commission-tracker-webhook.onrender.com` is classified as `missing-backend-attachment` with `HTTP 404` and `x-render-routing=no-server` on `/health`.
- Added a new `render_incident_signature` section to the smoke-check output so the handoff now states, in one line, whether the failure pattern isolates cleanly to external Render routing/domain binding versus a repo-side regression.
- Added a new `render_recovery_playbook` section to the smoke-check output so the generated artifact now gives ops an ordered recovery sequence starting with webhook domain attachment, then deploy contract verification, then secret loading, then the final ready-for-live-e2e gate.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 173/173
- Fresh artifacts:
  - `docs/smoke-checks/latest-trial-signup-smoke-check.json`
  - `docs/smoke-checks/latest-trial-signup-smoke-check.md`
- Current blocker remains external in production: `https://commission-tracker-webhook.onrender.com` still returns `404 Not Found` with `x-render-routing: no-server` on `/`, `/health`, `/test`, and `/stripe-webhook`, and the new incident signature flags that split as an external Render service/domain binding problem rather than an app-code route regression. This shell still lacks the live Stripe, Resend, service-role Supabase, Render app URL, and webhook SMTP values needed to complete the live verification path.
- Added a `change_summary` section to the smoke-check JSON and Markdown outputs so each fresh run now compares itself to the previous artifact instead of forcing ops to diff snapshots manually.
- Added an `unchanged_blocked_streak` counter so repeated blocked runs with no recovery now accumulate visibly in the artifact instead of reading like isolated one-off failures.

## Conclusion
Status: **Blocked for full live end-to-end confirmation**

Reason:
- Live webhook health endpoint returns 404 and Render fingerprints the hostname with `x-render-routing: no-server`
- Local webhook import verification is also blocked in this shell because `flask` and `stripe` are not installed
- Required live Stripe/email secrets are not available in the current workspace session

Latest artifact refresh:
- `docs/smoke-checks/trial-signup-smoke-check-2026-04-02T1714ET.json`
- `docs/smoke-checks/trial-signup-smoke-check-2026-04-02T1714ET.md`

Automated coverage status: **Pass**
Deployment/runtime validation status: **Blocked pending webhook restoration and a shell with webhook dependencies/secrets**
