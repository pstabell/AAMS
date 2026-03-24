# 2026-03-24: Legal Acceptance Checkboxes Before Stripe Checkout

## Summary
Added explicit Terms of Service and Privacy Policy acceptance checkboxes to the solo-agent subscription flow, required before the "Start Free Trial" button can proceed to Stripe checkout.

## Changes

### `auth_helpers.py` — `show_subscribe_tab()`
- Added two required checkboxes inside the `subscribe_form`:
  - "I have read and agree to the [Terms of Service](?page=terms)"
  - "I have read and agree to the [Privacy Policy](?page=privacy)"
- Validation blocks checkout if either is unchecked (separate error messages for each).
- Consent metadata is now passed into `stripe.checkout.Session.create()` via the `metadata` field:
  ```
  accepted_terms:   "true"
  accepted_privacy: "true"
  accepted_at:      ISO-8601 UTC timestamp (e.g. "2026-03-24T15:30:00Z")
  terms_version:    "2024-12-06"
  privacy_version:  "2024-12-06"
  ```
  This metadata appears on the Stripe dashboard for each checkout session and is queryable via the Stripe API.

## Why
- Legal best-practice: users must affirmatively consent to legal terms before entering a paid subscription flow.
- The metadata in Stripe provides an audit trail of consent without requiring a separate database table.
- Checkbox labels link directly to the in-app Terms and Privacy pages (`?page=terms`, `?page=privacy`).

## No Database Changes Required
Consent is recorded in Stripe metadata. No schema migration needed.
