# 2026-03-24 — invoice.payment_succeeded webhook handler

## Summary

Added `invoice.payment_succeeded` webhook event handler to `webhook_server.py`.
This is the explicit complement to the existing `invoice.payment_failed` handler
and closes the gap where a `past_due` user who successfully pays their overdue
invoice could remain permanently locked out.

## Root Cause

`invoice.payment_failed` marks the user `past_due` (login blocked).
`customer.subscription.updated` fires with `status='active'` when the subscription
recovers, which would have restored access — but only if that event arrived and
was processed correctly.  There was no dedicated, belt-and-suspenders handler for
the "payment went through" moment itself.

## Fix

```python
elif event['type'] == 'invoice.payment_succeeded':
    invoice = event['data']['object']
    customer_id = invoice.get('customer')
    subscription_id = invoice.get('subscription')

    if subscription_id:           # ignore non-subscription (one-off) invoices
        supabase.table('users').update({
            'subscription_status': 'active',
            'subscription_updated_at': datetime.now().isoformat()
        }).eq('stripe_customer_id', customer_id).execute()
```

Non-subscription invoices (no `subscription` field) are skipped so a one-off
payment charge cannot accidentally flip a cancelled account back to active.

## Test Coverage

Four new unit tests added to `test_webhook_subscription_status.py`:

| Test | Assertion |
|------|-----------|
| `test_subscription_invoice_resolves_to_active` | Subscription invoices trigger `status='active'` |
| `test_non_subscription_invoice_skipped` | `subscription=None` → no DB update |
| `test_recovery_targets_correct_customer` | Update keyed on `stripe_customer_id` |
| `test_normalize_status_used_in_subscription_updated` | `_normalize_stripe_status` coverage |

Two additional tests for `_normalize_stripe_status()` added (`TestNormalizeStripeStatus`).

**Total tests: 41 (21 webhook + 20 checkout) — all pass.**

## Affected Files

- `webhook_server.py` — new `elif event['type'] == 'invoice.payment_succeeded'` block
- `test_webhook_subscription_status.py` — `TestNormalizeStripeStatus` + `TestPaymentSucceededRecovery` classes
