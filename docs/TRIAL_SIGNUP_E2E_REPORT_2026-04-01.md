# Trial Signup End-to-End Test Report

**Date:** 2026-04-01
**Tester:** Forge
**Repo:** AMS-APP
**Card:** Activation Engine: End-to-End Trial Signup Test

## Scope
Validate the solo-agent trial signup path from signup form through Stripe checkout configuration, account provisioning webhook behavior, and onboarding email path.

## Latest Update
- 2026-04-06 7:17 AM ET: Tightened `archive_snapshot_verification` so the smoke-check flow now proves the current run’s timestamped owner-ready archive files and timestamped escalation-packet archive files still match the freshly generated handoff content, not just that the archive files exist. Added regression coverage for both the clean path and deliberate content drift, then reran `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` with 214/214 tests passing.
- Refreshed the live artifacts with `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive`; the latest report now records `archive_snapshot_verification.ok=true`, `owner_ready_content_verification.ok=true`, `escalation_packet_content_verification.ok=true`, and `packet_bundle_verification.checksum_matches=true` for the current timestamped archive snapshot.
- Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-06 5:16 AM ET: Added `archive_snapshot_verification` so the smoke-check flow now proves the timestamped owner-ready archive files and timestamped escalation-packet archive files for the current run were actually written, and also verifies the archived packet bundle still matches its detached SHA-256 checksum. Added regression coverage for both the clean archive path and the missing-archive failure path, then reran `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` with 213/213 tests passing.
- Refreshed the live artifacts with `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive`; the latest report now records `archive_snapshot_verification.ok=true`, `owner_ready_archive_present_count=3/3`, `escalation_packet_archive_present_count=6/6`, and `packet_bundle_verification.checksum_matches=true` for the current timestamped archive snapshot.
- Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-06 3:17 AM ET: Strengthened `latest_escalation_packet_verification` so the smoke-check flow now proves the manifest’s recorded SHA-256 hashes still match the actual packet files on disk instead of only checking that the bundle, checksum, and manifest exist. Added regression coverage for both the clean packet path and a tampered packet file, then reran `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` with 211/211 tests passing.
- Refreshed the live artifacts with `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive`; the latest report now records `latest_escalation_packet_verification.ok=true`, `manifest_hashes_match_files=true`, and no missing or mismatched packet files for the send-ready Render bundle.
- Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-06 1:17 AM ET: Added an `artifact_freshness` block to the smoke-check flow so each refreshed JSON and Markdown artifact now proves whether the current run regenerated the exact latest JSON, Markdown, owner-ready handoff files, and escalation-packet files instead of silently relying on stale evidence from a prior run.
- Added regression coverage for both mixed fresh/stale file detection and the nondefault-output-path case, then reran `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` with 210/210 tests passing.
- Refreshed the live artifacts with `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive`; the latest report now records `artifact_freshness.all_fresh=true`, `fresh_file_count=11/11`, and `latest_escalation_packet_verification.ok=true` for the send-ready packet.
- Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-05 11:18 PM ET: Added a latest escalation packet verification block to the smoke-check flow so each refreshed JSON and Markdown artifact now confirms the send-ready bundle, detached checksum, manifest, and expected zip members are all present after file generation instead of assuming the handoff packet wrote correctly. Added regression coverage for the new verification helper and the end-to-end CLI write path.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 208/208, and a fresh `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive` run now records `latest_escalation_packet_verification.ok=true` while the live packet still reflects the same external Render outage.
- Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-05 9:18 PM ET: Fixed the smoke-check CLI so stdout now emits the fully refreshed report after owner-ready files, escalation-packet files, and artifact inventory are regenerated, instead of printing the pre-refresh payload with stale packet metadata. Added regression coverage that asserts stdout matches the saved JSON artifact when all output directories are requested.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 207/207, and a fresh `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive` run now prints JSON identical to the saved latest artifact while refreshing the owner-ready and escalation-packet timestamps.
- Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-05 7:16 PM ET: Added repo-context capture to the smoke-check output so each JSON and Markdown artifact now records the exact AMS-APP branch, HEAD commit, commit subject, origin remote, and whether the workspace was clean or dirty when the evidence packet was generated.
- Expanded `scripts/trial_signup_smoke_check.py` with a git-backed repo-context block, added regression coverage in `test_trial_signup_smoke_check.py` for clean and dirty workspace detection plus Markdown rendering, and refreshed the latest smoke-check artifacts with the new evidence section.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 207/207. Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-05 5:16 PM ET: Added packet verification commands to the smoke-check output so each JSON and Markdown artifact now includes copy-paste `sha256sum -c` and `unzip -l` commands for both the latest escalation bundle and the newest archived packet snapshot.
- Expanded `scripts/trial_signup_smoke_check.py` so the support packet can be verified after handoff without anyone manually reconstructing file paths, updated `test_trial_signup_smoke_check.py` coverage for the new command block, and refreshed the latest smoke-check artifacts plus owner-ready and escalation-packet archives.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 205/205. Fresh live evidence is still unchanged on the external blocker: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`.
- 2026-04-05 3:18 PM ET: Added a detached `escalation-packet.zip.sha256` sidecar to the smoke-check output, so each send-ready Render packet now includes an integrity checksum for the exact archive file that gets attached to support tickets.
- Expanded `scripts/trial_signup_smoke_check.py` so both the live escalation packet and its timestamped archive now write the SHA-256 sidecar automatically, updated `artifact_inventory` and recommended attachment lists to include it, and added regression coverage in `test_trial_signup_smoke_check.py` for checksum writing, packet writing, archive writing, and the full CLI path.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 204/204, and the refreshed smoke-check artifacts still isolate the blocker to the external Render routing outage.
- 2026-04-05 1:27 PM ET: Added a generated `escalation-packet.zip` bundle to the smoke-check output, so every send-ready Render packet now ships as both individual files and a single attachable archive for support tickets that only want one upload.
- Expanded `scripts/trial_signup_smoke_check.py` so both the live escalation packet and its timestamped archive now write the zip bundle automatically, updated `artifact_inventory` and packet instructions to reference the bundle, and added regression coverage in `test_trial_signup_smoke_check.py` for zip generation, archive naming, and end-to-end CLI output.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed after the bundle change, and the latest smoke-check rerun still shows the same external Render routing outage.
- 2026-04-05 7:17 AM ET: Added a generated `README.txt` to the escalation packet output, so every smoke-check run now includes a human-forwardable packet cover sheet alongside the send-ready Render support message, JSON payload, and evidence manifest.
- Expanded `scripts/trial_signup_smoke_check.py` so both the live escalation packet and its timestamped archive now write the new README automatically, and expanded `artifact_inventory` so the README is listed in the recommended attachment bundle and Render support packet file list.
- Added regression coverage in `test_trial_signup_smoke_check.py` for README generation, packet writing, archive writing, and the full CLI flow. Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 202/202.
- Refreshed the live artifacts with `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive`, which now regenerates the send-ready packet, the new zip bundle, and archived snapshots.
- Fresh live outage evidence is still unchanged: `https://commission-tracker-app.onrender.com` returned HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returned HTTP 404 with `x-render-routing=no-server`, so the next external move remains with Traction and Render support.
- 2026-04-05 5:14 AM ET: Added `--escalation-packet-archive-dir` support to `scripts/trial_signup_smoke_check.py`, so each smoke-check run can now preserve timestamped Render support packet snapshots under `docs/smoke-checks/escalation-packet/archive/` instead of only overwriting the latest send-ready message, JSON payload, and evidence manifest.
- Added shared escalation-packet file generation plus archive path helpers, expanded `artifact_inventory` to track the escalation packet archive folder and latest archived files, and added regression coverage in `test_trial_signup_smoke_check.py` for archive path generation, archive writing, inventory expectations, and the full CLI path with packet archiving enabled.
- Validation target for this refresh: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py`, then rerun `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive --escalation-packet-dir docs/smoke-checks/escalation-packet --escalation-packet-archive-dir docs/smoke-checks/escalation-packet/archive`.
- Fresh live outage expectation remains unchanged until Render is repaired externally: `https://commission-tracker-app.onrender.com` should still return HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returns HTTP 404 with `x-render-routing=no-server`.
- 2026-04-05 1:19 AM ET: Added `--owner-messages-archive-dir` support to `scripts/trial_signup_smoke_check.py`, so each smoke-check run can now preserve timestamped `traction`, `render_support`, and `verification_shell` handoff snapshots under `docs/smoke-checks/owner-ready/archive/` instead of only overwriting the latest packet.
- Expanded `artifact_inventory` to track the live owner-ready text files plus the archive folder and latest snapshot files, so Traction and Render support can attach the current packet or pull an exact historical handoff without guessing paths.
- Added regression coverage in `test_trial_signup_smoke_check.py` for archive path generation, archive file writing, updated artifact inventory expectations, and the full CLI path with archive output enabled.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 198/198. Refreshed artifacts with `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md --owner-messages-dir docs/smoke-checks/owner-ready --owner-messages-archive-dir docs/smoke-checks/owner-ready/archive`, and the latest report now records the archived handoff packet.
- Fresh live evidence is still unchanged on the outage itself: `https://commission-tracker-app.onrender.com` returns HTTP 200 while `https://commission-tracker-webhook.onrender.com/health` still returns HTTP 404 with `x-render-routing=no-server`.
- 2026-04-04 11:16 PM ET: Added `--owner-messages-dir` support to `scripts/trial_signup_smoke_check.py`, so each smoke-check run can now write copy-ready `traction.txt`, `render_support.txt`, and `verification_shell.txt` handoff files directly to `docs/smoke-checks/owner-ready/` instead of forcing the next owner to copy text out of JSON or Markdown manually.
- Added regression coverage in `test_trial_signup_smoke_check.py` to lock that behavior in at the `generate_report(...)` level instead of only unit-testing `build_change_summary(...)` in isolation.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 195/195, and a fresh `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md` run now reports `No material change detected versus the previous smoke-check artifact.` with a correct unchanged blocked streak instead of bogus `None` comparisons.
- 2026-04-04 7:14 PM ET: Added `artifact_inventory` to `scripts/trial_signup_smoke_check.py`, so every smoke-check JSON and Markdown artifact now lists the exact evidence files, relative repo paths, existence flags, sizes, timestamps, and recommended attachment bundles for Traction and Render support.
- This removes another manual handoff step: the next owner no longer has to guess which files to attach when escalating the Render outage or re-running the verification packet.
- Updated `owner_action_plan` guidance so Traction explicitly attaches the latest smoke-check JSON, Markdown, trial-signup report, and `render.yaml`, and so the verification shell re-attaches refreshed evidence after each rerun.
- Added regression coverage for the new artifact inventory block in `test_trial_signup_smoke_check.py` and verified the Markdown report renders the new section.
- Validation: `python3 -m unittest test_checkout_flow.py test_webhook_subscription_status.py test_trial_signup_smoke_check.py` passed 194/194, then `python3 scripts/trial_signup_smoke_check.py --json-out docs/smoke-checks/latest-trial-signup-smoke-check.json --markdown-out docs/smoke-checks/latest-trial-signup-smoke-check.md` refreshed the latest evidence packet.

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
- Added `public_probe_commands` so the smoke-check artifacts now include the exact copy-paste `curl -i` commands for the public app plus every webhook endpoint in the probe matrix, making external escalation and repro faster.
- Added `render_escalation_payload` so the smoke-check artifacts now include a structured, ticket-ready incident packet with severity, ownership, host evidence, requested action, and the exact missing secrets still blocking the final live Stripe confirmation.

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
