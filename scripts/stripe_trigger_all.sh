#!/bin/bash
set -euo pipefail

EVENTS=(
  "payment_intent.succeeded"
  "payment_intent.payment_failed"
  "customer.subscription.created"
  "customer.subscription.updated"
  "customer.subscription.deleted"
  "invoice.payment_succeeded"
  "invoice.payment_failed"
  "invoice.finalized"
  "charge.succeeded"
  "charge.failed"
  "charge.dispute.created"
  "customer.created"
  "customer.deleted"
  "checkout.session.completed"
  "payout.failed"
)

for event in "${EVENTS[@]}"; do
  echo "Triggering: $event"
  stripe trigger "$event"
  sleep 1
done

echo "Done. All ${#EVENTS[@]} events triggered."
