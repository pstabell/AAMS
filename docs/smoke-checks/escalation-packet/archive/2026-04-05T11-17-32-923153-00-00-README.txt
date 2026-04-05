AMS-APP Render Escalation Packet
Generated at: 2026-04-05T11:17:32.923153+00:00
Severity: critical
Owner: Traction
Destination: Render support

What this packet is:
A send-ready evidence bundle for the current Render webhook routing outage blocking live Stripe trial signup validation.

Primary requested action:
Confirm the webhook hostname is attached to commission-tracker-webhook, redeploy the service, and recheck /health until x-render-routing=no-server disappears.

Recommended packet files:
- docs/smoke-checks/latest-trial-signup-smoke-check.json
- docs/smoke-checks/latest-trial-signup-smoke-check.md
- render.yaml
- docs/smoke-checks/owner-ready/render_support.txt
- docs/smoke-checks/escalation-packet/render-support-message.txt
- docs/smoke-checks/escalation-packet/render-support-payload.json
- docs/smoke-checks/escalation-packet/evidence-manifest.json
- docs/smoke-checks/escalation-packet/README.txt

Broader recommended attachments:
- docs/smoke-checks/latest-trial-signup-smoke-check.json
- docs/smoke-checks/latest-trial-signup-smoke-check.md
- docs/TRIAL_SIGNUP_E2E_REPORT_2026-04-01.md
- render.yaml
- docs/smoke-checks/owner-ready/traction.txt
- docs/smoke-checks/owner-ready/render_support.txt
- docs/smoke-checks/escalation-packet/render-support-message.txt
- docs/smoke-checks/escalation-packet/render-support-payload.json
- docs/smoke-checks/escalation-packet/evidence-manifest.json
- docs/smoke-checks/escalation-packet/README.txt

Live verification shell still needs these secrets before the final Stripe test:
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_ID
- RESEND_API_KEY
- SUPABASE_SERVICE_KEY

If forwarding to Render support:
1. Send render-support-message.txt as the support message body.
2. Attach render-support-payload.json and evidence-manifest.json.
3. Include the latest smoke-check JSON/Markdown artifacts and render.yaml from the packet file list above.
