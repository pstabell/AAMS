# Trial Signup Smoke Check Snapshot

Generated at: 2026-04-06T11:17:39.594266+00:00
Ready for live e2e: NO

## Executive summary
- AMS-APP trial signup stack is still blocked. App host returned HTTP 200 OK while webhook health returned HTTP 404 Not Found.
- Render evidence: app attachment_state=healthy-attached with x-render-origin-server=TornadoServer/6.5.5, webhook attachment_state=missing-backend-attachment with x-render-routing=no-server.
- Repo-side checkout, webhook, and Render blueprint contracts are green while the app hostname is healthy-attached and the webhook hostname is missing-backend-attachment. This points to an external Render service or domain binding problem, not an app-code route regression.
- Live verification shell still needs secrets before the final Stripe run: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- Escalation: severity=critical owner=Traction destination=Render support unchanged_blocked_streak=30.
- Traction should escalate to Render support. Escalate immediately. The outage is externally isolated and has repeated without material recovery. Live E2E shell still needs secrets before the final Stripe confirmation: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY

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

## Repo context
- Git status: dirty
- Branch: main
- HEAD: e691cf9
- Head subject: feat: verify archived smoke-check snapshots
- Head committed at: 2026-04-06T05:17:07-04:00
- Origin: https://github.com/pstabell/AMS-APP.git
- Tracked changes: M scripts/trial_signup_smoke_check.py, M test_trial_signup_smoke_check.py

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

## Public webhook probe matrix
- path=/; status=404 Not Found; ok=NO; x-render-routing=no-server; x-render-origin-server=None; server=cloudflare; content-type=text/plain; charset=utf-8; body-preview=Not Found

- path=/health; status=404 Not Found; ok=NO; x-render-routing=no-server; x-render-origin-server=None; server=cloudflare; content-type=text/plain; charset=utf-8; body-preview=Not Found

- path=/stripe-webhook; status=404 Not Found; ok=NO; x-render-routing=no-server; x-render-origin-server=None; server=cloudflare; content-type=text/plain; charset=utf-8; body-preview=Not Found

- path=/test; status=404 Not Found; ok=NO; x-render-routing=no-server; x-render-origin-server=None; server=cloudflare; content-type=text/plain; charset=utf-8; body-preview=Not Found


## Public probe commands
- curl -i https://commission-tracker-app.onrender.com
- curl -i https://commission-tracker-webhook.onrender.com/
- curl -i https://commission-tracker-webhook.onrender.com/health
- curl -i https://commission-tracker-webhook.onrender.com/stripe-webhook
- curl -i https://commission-tracker-webhook.onrender.com/test

## Change summary versus previous smoke check
- Previous artifact generated at: 2026-04-06T09:16:43.540983+00:00
- Material change detected: NO
- Unchanged blocked streak: 30
- No material change detected versus the previous smoke-check artifact.

## Incident history
- Artifact count considered: 14
- Blocked artifact count: 14
- Latest status: blocked
- First blocked at: 2026-04-02T05:17:10.778608+00:00
- First no-server at: 2026-04-02T07:18:14.875837+00:00
- Current state started at: 2026-04-02T07:18:14.875837+00:00
- Blocked duration: 4d 6h 0m
- No-server duration: 4d 3h 59m
- Current state duration: 4d 3h 59m

## Render incident signature
- Repo contract OK: YES
- App host attachment state: healthy-attached
- Webhook host attachment state: missing-backend-attachment
- External routing issue isolated: YES
- Conclusion: Repo-side checkout, webhook, and Render blueprint contracts are green while the app hostname is healthy-attached and the webhook hostname is missing-backend-attachment. This points to an external Render service or domain binding problem, not an app-code route regression.

## Render support packet
- Incident type: render-webhook-routing-outage
- Requested action: Confirm the webhook hostname is attached to commission-tracker-webhook, redeploy the service, and recheck /health until x-render-routing=no-server disappears.
- commission-tracker-app: host=commission-tracker-app.onrender.com; probe_path=/; status=200 OK; attachment_state=healthy-attached; x-render-origin-server=TornadoServer/6.5.5; x-render-routing=None; cf-ray=9e80632be9b7e601-IAD; date=Mon, 06 Apr 2026 11:17:39 GMT
- commission-tracker-webhook: host=commission-tracker-webhook.onrender.com; probe_path=/health; status=404 Not Found; attachment_state=missing-backend-attachment; x-render-origin-server=None; x-render-routing=no-server; cf-ray=9e80632cfc9f28a2-IAD; date=Mon, 06 Apr 2026 11:17:40 GMT

## Escalation recommendation
- Severity: critical
- Owner: Traction
- Destination: Render support
- Unchanged blocked streak: 30
- Urgency: Escalate immediately. The outage is externally isolated and has repeated without material recovery.
- Prerequisite: Live E2E shell still needs secrets before the final Stripe confirmation: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- Recommended message: Traction should escalate to Render support. Escalate immediately. The outage is externally isolated and has repeated without material recovery. Live E2E shell still needs secrets before the final Stripe confirmation: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY

## Artifact refresh commands
- json: python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json
- markdown: python3 scripts/trial_signup_smoke_check.py --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md
- both: python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md

## Packet verification commands
- latest_bundle:
  - cd . && sha256sum -c docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256
  - cd . && unzip -l docs/smoke-checks/escalation-packet/escalation-packet.zip
- archived_bundle:
  - cd . && latest_checksum=$(ls -1t docs/smoke-checks/escalation-packet/archive/*-escalation-packet.zip.sha256 | head -n 1)
  - cd . && sha256sum -c "$latest_checksum"
  - cd . && latest_bundle=${latest_checksum%.sha256} && unzip -l "$latest_bundle"

## Artifact freshness
- All tracked files fresh for this run: YES
- Fresh file count: 11/11
- Missing labels: None
- Stale labels: None

## Latest escalation packet verification
- Overall status: PASS
- Bundle exists: YES
- Checksum exists: YES
- Manifest exists: YES
- Checksum matches bundle: YES
- Manifest packet hash count: 5
- Manifest lists bundle checksum: YES
- Manifest hashes match files: YES
- Manifest missing hash files: None
- Manifest mismatched hash files: None
- Bundle members: README.txt, evidence-manifest.json, render-support-message.txt, render-support-payload.json
- Missing bundle members: None

## Archive snapshot verification
- Overall status: FAIL
- Owner-ready archive present: 3/3
- Escalation-packet archive present: 6/6
- Owner-ready archive content matches latest: YES
- Owner-ready matching files: traction, render_support, verification_shell
- Owner-ready mismatched files: None
- Escalation-packet archive content matches latest: NO
- Escalation-packet matching files: render-support-message.txt, render-support-payload.json
- Escalation-packet mismatched files: evidence-manifest.json, README.txt
- Archived bundle checksum matches: YES
- Missing archive files: None
- Archived bundle path: docs/smoke-checks/escalation-packet/archive/2026-04-06T11-17-39-594266-00-00-escalation-packet.zip
- Archived checksum path: docs/smoke-checks/escalation-packet/archive/2026-04-06T11-17-39-594266-00-00-escalation-packet.zip.sha256

## Artifact inventory
- latest_json: path=docs/smoke-checks/latest-trial-signup-smoke-check.json; exists=YES; size_bytes=48012; modified_at=2026-04-06T11:17:40.909796+00:00
- latest_markdown: path=docs/smoke-checks/latest-trial-signup-smoke-check.md; exists=YES; size_bytes=31405; modified_at=2026-04-06T11:17:40.910337+00:00
- trial_signup_report: path=docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md; exists=YES; size_bytes=29614; modified_at=2026-04-06T09:17:01.250095+00:00
- render_blueprint: path=render.yaml; exists=YES; size_bytes=2080; modified_at=2026-04-03T01:15:05.095488+00:00
- smoke_check_script: path=scripts/trial_signup_smoke_check.py; exists=YES; size_bytes=128042; modified_at=2026-04-06T11:15:54.829088+00:00
- smoke_check_tests: path=test_trial_signup_smoke_check.py; exists=YES; size_bytes=118669; modified_at=2026-04-06T11:17:22.200008+00:00
- owner_ready_traction: path=docs/smoke-checks/owner-ready/traction.txt; exists=YES; size_bytes=651; modified_at=2026-04-06T11:17:40.911636+00:00
- owner_ready_render_support: path=docs/smoke-checks/owner-ready/render_support.txt; exists=YES; size_bytes=726; modified_at=2026-04-06T11:17:40.911785+00:00
- owner_ready_verification_shell: path=docs/smoke-checks/owner-ready/verification_shell.txt; exists=YES; size_bytes=584; modified_at=2026-04-06T11:17:40.911914+00:00
- escalation_packet_message: path=docs/smoke-checks/escalation-packet/render-support-message.txt; exists=YES; size_bytes=2406; modified_at=2026-04-06T11:17:40.920357+00:00
- escalation_packet_payload: path=docs/smoke-checks/escalation-packet/render-support-payload.json; exists=YES; size_bytes=1392; modified_at=2026-04-06T11:17:40.920507+00:00
- escalation_packet_manifest: path=docs/smoke-checks/escalation-packet/evidence-manifest.json; exists=YES; size_bytes=10069; modified_at=2026-04-06T11:17:40.922689+00:00
- escalation_packet_readme: path=docs/smoke-checks/escalation-packet/README.txt; exists=YES; size_bytes=3242; modified_at=2026-04-06T11:17:40.922848+00:00
- escalation_packet_bundle_checksum: path=docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256; exists=YES; size_bytes=88; modified_at=2026-04-06T11:17:40.924322+00:00
- owner_ready_archive: path=docs/smoke-checks/owner-ready/archive; exists=YES; size_bytes=None; modified_at=None
- escalation_packet_dir: path=docs/smoke-checks/escalation-packet; exists=YES; size_bytes=None; modified_at=None
- escalation_packet_bundle: path=docs/smoke-checks/escalation-packet/escalation-packet.zip; exists=YES; size_bytes=4809; modified_at=2026-04-06T11:17:40.923340+00:00
- escalation_packet_archive: path=docs/smoke-checks/escalation-packet/archive; exists=YES; size_bytes=None; modified_at=None
- recommended_attachments: docs/smoke-checks/latest-trial-signup-smoke-check.json, docs/smoke-checks/latest-trial-signup-smoke-check.md, docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md, render.yaml, docs/smoke-checks/owner-ready/traction.txt, docs/smoke-checks/owner-ready/render_support.txt, docs/smoke-checks/escalation-packet/render-support-message.txt, docs/smoke-checks/escalation-packet/render-support-payload.json, docs/smoke-checks/escalation-packet/evidence-manifest.json, docs/smoke-checks/escalation-packet/README.txt, docs/smoke-checks/escalation-packet/escalation-packet.zip, docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256
- render_support_packet_files: docs/smoke-checks/latest-trial-signup-smoke-check.json, docs/smoke-checks/latest-trial-signup-smoke-check.md, render.yaml, docs/smoke-checks/owner-ready/render_support.txt, docs/smoke-checks/escalation-packet/render-support-message.txt, docs/smoke-checks/escalation-packet/render-support-payload.json, docs/smoke-checks/escalation-packet/evidence-manifest.json, docs/smoke-checks/escalation-packet/README.txt, docs/smoke-checks/escalation-packet/escalation-packet.zip, docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256
- traction_handoff_files: docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md, docs/smoke-checks/latest-trial-signup-smoke-check.md, docs/smoke-checks/latest-trial-signup-smoke-check.json, docs/smoke-checks/owner-ready/traction.txt, docs/smoke-checks/escalation-packet/render-support-message.txt, docs/smoke-checks/escalation-packet/evidence-manifest.json, docs/smoke-checks/escalation-packet/escalation-packet.zip.sha256

## Escalation packet hashes
- render-support-message.txt: sha256=9403f3d27da327b4c9952239f52f50da3bcd3a1dddd9d51ec3b0cd23f78e8b6d; size_bytes=2406; path=None
- render-support-payload.json: sha256=82083aa1c2f8fba2b168b3e6243b9a7e4ef5d4a6206c5f1063652ab9c50e32b3; size_bytes=1392; path=None
- evidence-manifest.json: sha256=6a5db8a95d888cdb5f6a7807b17c5ddfb472dbd45c76e37cb671eb3e5f592f01; size_bytes=10069; path=None
- README.txt: sha256=a859590d23f141fc2bc46f06f3ebed050356580e59407eb5426b747261c96aa2; size_bytes=3140; path=None
- latest-trial-signup-smoke-check.json: sha256=12ba2cba8923eda75d0ef37e1a12cfae424c421055d5a2793a3fd97c7d95956f; size_bytes=48012; path=docs/smoke-checks/latest-trial-signup-smoke-check.json
- latest-trial-signup-smoke-check.md: sha256=585bc8349190167edc2159465464cbc6ff0771ecbbde0fb948b84ecbece4befb; size_bytes=31405; path=docs/smoke-checks/latest-trial-signup-smoke-check.md

## Owner action plan
- traction:
  - Forward the Render escalation message and support packet without rewriting the evidence.
  - Attach the latest smoke-check JSON, smoke-check Markdown, trial-signup report, and render.yaml from the artifact inventory.
  - Tell Render support the app host commission-tracker-app.onrender.com/ is healthy while the webhook host commission-tracker-webhook.onrender.com/health is still detached or unrouted.
  - Ask Render to confirm the webhook hostname is attached to commission-tracker-webhook and redeploy the service.
  - Load or coordinate the missing app-shell runtime values before the final live test: APP_ENVIRONMENT, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, SUPABASE_SERVICE_KEY
  - Load or coordinate the missing webhook-shell runtime values before the final live test: APP_ENVIRONMENT, FROM_EMAIL, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, SUPABASE_SERVICE_KEY
- render_support:
  - Confirm commission-tracker-webhook.onrender.com is attached to commission-tracker-webhook, not a stale or missing backend.
  - Redeploy commission-tracker-webhook and verify the runtime comes up healthy behind the public hostname.
  - Recheck https://commission-tracker-webhook.onrender.com/health until x-render-routing=no-server disappears and the endpoint returns 200.
- verification_shell:
  - Re-run python3 scripts/trial_signup_smoke_check.py after Render reports the webhook deploy is healthy.
  - Refresh the JSON and Markdown smoke-check artifacts before attempting any live Stripe path.
  - Use the artifact inventory to attach the updated evidence files to the handoff after each rerun.
  - Export the missing live E2E secrets before the final test: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
  - Only run a real Stripe test-mode signup after ready_for_live_e2e flips to true.

## Owner ready messages
- traction: Traction handoff at 2026-04-06T11:17:39.594266+00:00: commission-tracker-app.onrender.com/ is healthy at HTTP 200 while commission-tracker-webhook.onrender.com/health is still HTTP 404 with x-render-routing=no-server. Forward the attached Render escalation packet, ask Render to confirm the webhook hostname is attached to commission-tracker-webhook, redeploy it, and then have the verification shell rerun the smoke check. Next actions: Forward the Render escalation message and support packet without rewriting the evidence. Attach the latest smoke-check JSON, smoke-check Markdown, trial-signup report, and render.yaml from the artifact inventory.
- render_support: Render support request generated 2026-04-06T11:17:39.594266+00:00: commission-tracker-app.onrender.com/ is healthy at HTTP 200 with attachment_state=healthy-attached, but commission-tracker-webhook.onrender.com/health is HTTP 404 with attachment_state=missing-backend-attachment and x-render-routing=no-server. Please confirm commission-tracker-webhook owns the webhook hostname, redeploy the service, and retest /health until the route returns 200 without x-render-routing=no-server. Next actions: Confirm commission-tracker-webhook.onrender.com is attached to commission-tracker-webhook, not a stale or missing backend. Redeploy commission-tracker-webhook and verify the runtime comes up healthy behind the public hostname.
- verification_shell: Verification-shell handoff: rerun python3 scripts/trial_signup_smoke_check.py after Render reports the webhook service healthy, refresh the JSON and Markdown artifacts, and only run the real Stripe test-mode signup after ready_for_live_e2e turns true. Missing live E2E secrets: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY. Next actions: Re-run python3 scripts/trial_signup_smoke_check.py after Render reports the webhook deploy is healthy. Refresh the JSON and Markdown smoke-check artifacts before attempting any live Stripe path.

## Render recovery playbook
- 1. Render dashboard: open commission-tracker-webhook first because the smoke check isolated the incident to the webhook hostname, not the main app.
- 2. Custom Domains: confirm commission-tracker-webhook.onrender.com is attached to commission-tracker-webhook while commission-tracker-app.onrender.com remains attached to commission-tracker-app.
- 3. If the webhook hostname is missing or attached to the wrong service, remove the stale attachment, reattach it to commission-tracker-webhook, and save.
- 4. Build & Deploy: confirm the deployed start command is gunicorn webhook_server:app --bind 0.0.0.0:${PORT} and trigger a manual deploy if Render has stale runtime state.
- 5. Wait for Render to report a healthy instance, then probe /health again before attempting any Stripe flow.
- 6. Load the missing webhook runtime values in Render or the verification shell: APP_ENVIRONMENT, FROM_EMAIL, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, SUPABASE_SERVICE_KEY
- 7. Before the real signup test, load the remaining live E2E secrets into the verification shell: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- 8. Re-run python3 scripts/trial_signup_smoke_check.py and only run a real Stripe test-mode signup after ready_for_live_e2e flips to true.

## Recovery exit criteria
- commission-tracker-app.onrender.com/ returns HTTP 200 from the public app host.
- commission-tracker-webhook.onrender.com/health returns HTTP 200 without x-render-routing=no-server.
- The local webhook /health import check returns HTTP 200 from webhook_server.py.
- The checked-in checkout, webhook service, and Render blueprint contract checks all remain green.
- The webhook hostname is attached to commission-tracker-webhook in Render and shows a healthy backend instance.
- The verification shell has the live Stripe, Resend, and Supabase secrets loaded: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- A fresh smoke-check artifact reports ready_for_live_e2e=true.
- One real Stripe test-mode signup completes and the follow-up evidence captures the session ID, webhook timestamp, and onboarding email result.

## Render escalation message
Render support request for AMS-APP webhook routing outage.
Generated at 2026-04-06T11:17:39.594266+00:00.
Repo-side checkout, webhook, and Render blueprint contracts are green while the app hostname is healthy-attached and the webhook hostname is missing-backend-attachment. This points to an external Render service or domain binding problem, not an app-code route regression.
Healthy app host evidence: commission-tracker-app.onrender.com/ -> HTTP 200 OK with attachment_state=healthy-attached and x-render-origin-server=TornadoServer/6.5.5.
Broken webhook host evidence: commission-tracker-webhook.onrender.com/health -> HTTP 404 Not Found with attachment_state=missing-backend-attachment and x-render-routing=no-server.
Requested action: Confirm the webhook hostname is attached to commission-tracker-webhook, redeploy the service, and recheck /health until x-render-routing=no-server disappears.
Recommended recovery steps:
- 1. Render dashboard: open commission-tracker-webhook first because the smoke check isolated the incident to the webhook hostname, not the main app.
- 2. Custom Domains: confirm commission-tracker-webhook.onrender.com is attached to commission-tracker-webhook while commission-tracker-app.onrender.com remains attached to commission-tracker-app.
- 3. If the webhook hostname is missing or attached to the wrong service, remove the stale attachment, reattach it to commission-tracker-webhook, and save.
- 4. Build & Deploy: confirm the deployed start command is gunicorn webhook_server:app --bind 0.0.0.0:${PORT} and trigger a manual deploy if Render has stale runtime state.
- 5. Wait for Render to report a healthy instance, then probe /health again before attempting any Stripe flow.
- 6. Load the missing webhook runtime values in Render or the verification shell: APP_ENVIRONMENT, FROM_EMAIL, PRODUCTION_SUPABASE_ANON_KEY, PRODUCTION_SUPABASE_SERVICE_KEY, PRODUCTION_SUPABASE_URL, RENDER_APP_URL, RESEND_API_KEY, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER, STRIPE_PRICE_ID, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, SUPABASE_SERVICE_KEY
- 7. Before the real signup test, load the remaining live E2E secrets into the verification shell: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- 8. Re-run python3 scripts/trial_signup_smoke_check.py and only run a real Stripe test-mode signup after ready_for_live_e2e flips to true.

## Render escalation payload
- ticket_title: AMS-APP Render webhook routing outage blocks live Stripe signup path
- severity: critical
- owner: Traction
- destination: Render support
- generated_at: 2026-04-06T11:17:39.594266+00:00
- incident_type: render-webhook-routing-outage
- unchanged_blocked_streak: 30
- repo_contract_ok: True
- external_routing_issue: True
- app_host_evidence: commission-tracker-app.onrender.com/ -> HTTP 200 OK attachment_state=healthy-attached x-render-origin-server=TornadoServer/6.5.5
- webhook_host_evidence: commission-tracker-webhook.onrender.com/health -> HTTP 404 Not Found attachment_state=missing-backend-attachment x-render-routing=no-server
- requested_action: Confirm the webhook hostname is attached to commission-tracker-webhook, redeploy the service, and recheck /health until x-render-routing=no-server disappears.
- recommended_message: Traction should escalate to Render support. Escalate immediately. The outage is externally isolated and has repeated without material recovery. Live E2E shell still needs secrets before the final Stripe confirmation: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY
- missing_live_e2e_secrets: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, RESEND_API_KEY, SUPABASE_SERVICE_KEY

## Probe previews
- Webhook health preview: Not Found

- Webhook root preview: Not Found

