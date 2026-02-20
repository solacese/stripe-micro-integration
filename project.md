# Project: stripe-solace-bridge
## Mission
Build a production-grade, fully async Python micro-service that ingests Stripe webhook
events and publishes them to a Solace PubSub+ Event Broker with guaranteed delivery,
structured topic taxonomy, dead-letter queue support, idempotency, observability, and
a complete end-to-end test and validation suite. This project must be fully runnable
from a single `make e2e` command with zero manual steps after env setup.

---

## Tech Stack
- **Python 3.11+**
- **FastAPI** (async ASGI webhook receiver)
- **stripe** Python SDK (signature verification + event triggering)
- **solace-pubsubplus** (PubSub+ Messaging API for Python)
- **Pydantic v2** (config + schema validation)
- **structlog** (structured JSON logging)
- **prometheus_client** (metrics)
- **pytest + pytest-asyncio + httpx** (test suite)
- **Redis** (idempotency store; can be replaced with in-memory LRU)
- **Docker + docker-compose + Helm chart**
- **Makefile** (developer task runner)

---

## Project Structure
```
stripe-solace-bridge/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── lifespan.py
│   ├── models/
│   │   ├── stripe_event.py
│   │   └── solace_message.py
│   ├── services/
│   │   ├── stripe_verifier.py
│   │   ├── solace_publisher.py
│   │   ├── solace_subscriber.py       # NEW: used by validation suite to consume
│   │   ├── event_router.py
│   │   ├── idempotency.py
│   │   └── async_processor.py
│   ├── handlers/
│   │   ├── base.py
│   │   ├── payment_intent.py
│   │   ├── charge.py
│   │   ├── customer.py
│   │   ├── subscription.py
│   │   ├── invoice.py
│   │   ├── dispute.py
│   │   ├── payout.py
│   │   └── checkout.py
│   ├── middleware/
│   │   ├── logging_middleware.py
│   │   └── metrics_middleware.py
│   └── api/
│       ├── webhook.py
│       └── health.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   └── stripe_events/           # One .json per event type
│   │       ├── payment_intent.succeeded.json
│   │       ├── payment_intent.payment_failed.json
│   │       ├── customer.subscription.created.json
│   │       ├── customer.subscription.updated.json
│   │       ├── customer.subscription.deleted.json
│   │       ├── invoice.payment_succeeded.json
│   │       ├── invoice.payment_failed.json
│   │       ├── charge.succeeded.json
│   │       ├── charge.failed.json
│   │       ├── charge.dispute.created.json
│   │       ├── customer.created.json
│   │       ├── customer.deleted.json
│   │       ├── checkout.session.completed.json
│   │       └── payout.failed.json
│   ├── unit/
│   │   ├── test_stripe_verifier.py
│   │   ├── test_event_router.py
│   │   ├── test_idempotency.py
│   │   ├── test_solace_publisher.py
│   │   └── test_handlers/
│   │       ├── test_payment_intent.py
│   │       ├── test_subscription.py
│   │       └── test_invoice.py
│   ├── integration/
│   │   ├── test_webhook_endpoint.py
│   │   └── test_solace_roundtrip.py
│   └── e2e/
│       ├── conftest_e2e.py           # E2E fixtures: live broker + Stripe CLI
│       ├── test_e2e_pipeline.py      # Full pipeline: trigger → bridge → queue
│       ├── test_e2e_idempotency.py   # Duplicate event → only 1 message on queue
│       ├── test_e2e_dmq.py           # Poison message → ends up on DMQ
│       ├── test_e2e_reconnect.py     # Broker restart → bridge reconnects, no loss
│       └── test_e2e_metrics.py       # Prometheus counters match event count
├── scripts/
│   ├── provision_solace.py          # SEMP v2 idempotent provisioning
│   ├── stripe_trigger_all.sh        # Fire every supported event type via CLI
│   ├── validate_pipeline.py         # Standalone smoke-test script
│   └── consume_queue.py             # CLI tool to read messages from any queue
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docker-compose.e2e.yml           # Override for E2E: Stripe CLI container
├── helm/
│   └── stripe-solace-bridge/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           └── secret.yaml
├── Makefile
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## Configuration (.env.example)
```env
# Stripe
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_API_KEY=sk_test_...

# Solace Broker
SOLACE_HOST=tcp://your-broker-host:55555
SOLACE_SEMP_HOST=http://your-broker-host:8080
SOLACE_SEMP_USERNAME=admin
SOLACE_SEMP_PASSWORD=admin
SOLACE_VPN=default
SOLACE_USERNAME=stripe-bridge-user
SOLACE_PASSWORD=your-password
SOLACE_TLS_ENABLED=false
SOLACE_TLS_CA_CERT_PATH=

# App
APP_PORT=8080
LOG_LEVEL=INFO
IDEMPOTENCY_TTL_SECONDS=86400
ASYNC_QUEUE_SIZE=1000
MAX_PUBLISH_RETRIES=3
RETRY_BACKOFF_BASE_SECONDS=0.5
DMQ_ELIGIBLE=true

# E2E Test Config
E2E_STRIPE_ACCOUNT_ID=acct_xxx
E2E_CONSUME_TIMEOUT_SECONDS=10
E2E_QUEUE_DRAIN_BEFORE_TEST=true
```

---

## Solace Topic Taxonomy

```
stripe/webhook/v1/{event_category}/{event_type_suffix}/{account_id}
```

Examples:
```
stripe/webhook/v1/payment_intent/succeeded/acct_xxx
stripe/webhook/v1/payment_intent/payment_failed/acct_xxx
stripe/webhook/v1/subscription/created/acct_xxx
stripe/webhook/v1/subscription/updated/acct_xxx
stripe/webhook/v1/subscription/deleted/acct_xxx
stripe/webhook/v1/invoice/payment_succeeded/acct_xxx
stripe/webhook/v1/invoice/payment_failed/acct_xxx
stripe/webhook/v1/invoice/finalized/acct_xxx
stripe/webhook/v1/charge/succeeded/acct_xxx
stripe/webhook/v1/charge/failed/acct_xxx
stripe/webhook/v1/charge/dispute/created/acct_xxx
stripe/webhook/v1/customer/created/acct_xxx
stripe/webhook/v1/customer/deleted/acct_xxx
stripe/webhook/v1/checkout/session/completed/acct_xxx
stripe/webhook/v1/payout/failed/acct_xxx
stripe/webhook/v1/error/unroutable/acct_xxx
```

---

## Solace Publisher (services/solace_publisher.py)

Implement a `SolacePublisher` class with:

1. **Connection management**:
   - `MessagingService.builder()` with `RetryUntilElapsed(total_wait_ms=300_000,
     retry_interval_ms=1000)` reconnection strategy
   - Optional TLS with CA cert
   - Connect on lifespan startup, disconnect on shutdown
   - Thread-safe singleton pattern

2. **PersistentMessagePublisher**:
   - `DMQEligible=True` on every message
   - `TimeToLive` from config (default 0 = infinite)
   - Message properties:
     - `CorrelationId`: Stripe `event.id`
     - `ApplicationMessageId`: Stripe `event.id`
     - `ContentType`: `application/json`
     - User properties: `stripe_api_version`, `stripe_account_id`,
       `event_created_at`, `bridge_received_at`
   - `PublishReceiptListener` for async ack logging

3. **Publish method**:
   ```python
   async def publish(self, topic: str, payload: dict, event_id: str) -> None
   ```
   - Retry with exponential backoff on failure
   - After max retries: log + increment `solace_publish_failures_total`
   - Never raise an exception that would return non-200 to Stripe

---

## Solace Subscriber (services/solace_subscriber.py)

Implement a `SolaceSubscriber` class used exclusively by the validation suite and
`scripts/consume_queue.py`:

```python
class SolaceSubscriber:
    async def consume_one(
        self,
        queue_name: str,
        timeout_seconds: float = 10.0
    ) -> dict | None:
        """
        Bind to a durable queue, receive one persistent message,
        ACK it, and return the deserialized JSON payload.
        Returns None on timeout.
        """

    async def consume_n(
        self,
        queue_name: str,
        n: int,
        timeout_seconds: float = 15.0
    ) -> list[dict]:
        """
        Receive exactly n messages or as many as arrive before timeout.
        """

    async def drain_queue(self, queue_name: str) -> int:
        """
        Consume and ACK all available messages. Returns count drained.
        Used in E2E test setup to ensure clean state.
        """
```

Use `PersistentMessageReceiver` with `MissingResourcesCreationStrategy.NEVER`
(queues must already exist via provisioning script).

---

## Webhook Receiver (api/webhook.py)

```
POST /webhooks/stripe
```

1. Read raw body bytes
2. Verify `Stripe-Signature` header → return 400 on failure
3. Return `200 OK` immediately
4. Push verified `stripe.Event` onto `AsyncProcessor` queue
5. If queue is full → return `429 Too Many Requests`
   with `Retry-After: 5` header

---

## Async Processor (services/async_processor.py)

Background `asyncio.Task` processing pipeline per event:
1. Idempotency check → skip + log if duplicate
2. Route → `event_router.get_topic(event.type, event.account)`
3. Enrich → add `bridge_received_at`, `bridge_version`, `trace_id`
4. Dispatch to handler → returns normalized payload dict
5. Publish to Solace
6. Mark idempotency
7. Increment metrics

Graceful shutdown: drain queue with configurable timeout.

---

## Event Handlers

Each handler extends `BaseEventHandler` and returns a normalized envelope:

```json
{
  "event_id": "evt_xxx",
  "event_type": "payment_intent.succeeded",
  "api_version": "2023-10-16",
  "account_id": "acct_xxx",
  "created_at": 1708000000,
  "bridge_received_at": "2026-02-20T14:07:00Z",
  "bridge_version": "1.0.0",
  "trace_id": "uuid4",
  "data": { /* normalized fields */ },
  "raw": { /* full event.data.object */ }
}
```

Implement handlers with specific field extraction for:
- `PaymentIntentHandler`: id, amount, currency, status, customer, payment_method,
  metadata, last_payment_error
- `SubscriptionHandler`: id, customer, status, current_period_start/end, plan,
  cancel_at_period_end, trial_end, items
- `InvoiceHandler`: id, customer, subscription, amount_due, amount_paid, status,
  lines summary, attempt_count
- `ChargeHandler`: id, amount, currency, status, outcome, risk_level, risk_score
- `DisputeHandler`: id, charge, amount, reason, status, evidence_due_by
- `CustomerHandler`: id, email, name, metadata, default_source
- `CheckoutSessionHandler`: id, customer, mode, payment_status, amount_total,
  metadata, line_items summary
- `PayoutHandler`: id, amount, currency, status, arrival_date, failure_message

---

## Broker Provisioning (scripts/provision_solace.py)

Use SEMP v2 REST API to idempotently provision:

1. **Queues**:
   - `stripe.payments.inbound` → subscription `stripe/webhook/v1/payment_intent/>`
   - `stripe.subscriptions.inbound` → `stripe/webhook/v1/subscription/>`
   - `stripe.invoices.inbound` → `stripe/webhook/v1/invoice/>`
   - `stripe.customers.inbound` → `stripe/webhook/v1/customer/>`
   - `stripe.all.inbound` → `stripe/webhook/v1/>` (catch-all audit)
   - `stripe.errors.dmq` → Dead Message Queue

2. **Queue settings** for all queues:
   - `accessType`: `non-exclusive`
   - `maxMsgSpoolUsage`: 5000 MB
   - `maxRedeliveryCount`: 5
   - `deadMsgQueue`: `stripe.errors.dmq`
   - `permission`: `consume`

3. **ACL Profile**: `stripe-bridge-acl` (publish to `stripe/webhook/v1/>`)

4. **Client Profile**: `stripe-bridge-client-profile`

Script must be idempotent (GET-before-POST). Accept credentials via env vars or
`--semp-host`, `--username`, `--password`, `--vpn` CLI args. Print a summary table.

---

## Observability

### Prometheus Metrics (GET /metrics)
- `stripe_webhooks_received_total{event_type}` — Counter
- `stripe_webhooks_verified_total` — Counter
- `stripe_webhooks_invalid_signature_total` — Counter
- `stripe_events_processed_total{event_type, status}` — Counter
- `solace_publish_attempts_total{topic, status}` — Counter
- `solace_publish_failures_total{topic}` — Counter
- `solace_connection_status` — Gauge (1=connected, 0=disconnected)
- `async_queue_size` — Gauge
- `event_processing_duration_seconds{event_type}` — Histogram

### Health Endpoints
- `GET /health` → `{"status": "ok", "uptime_seconds": ...}`
- `GET /ready` → 200 if Solace connected, 503 if not
- `GET /metrics` → Prometheus text

---

## Unit Tests (tests/unit/)

- `test_stripe_verifier.py`:
  - Valid signature + body → parses event correctly
  - Tampered body → raises `WebhookVerificationError`
  - Missing `Stripe-Signature` header → 400
  - Timestamp outside tolerance window → 400

- `test_event_router.py`:
  - All 14+ supported event types → assert exact expected topic string
  - Unknown event type → `stripe/webhook/v1/error/unroutable/{account_id}`
  - Account ID is always embedded in topic as last segment

- `test_idempotency.py`:
  - First call `is_duplicate("evt_123")` → False
  - Second call `is_duplicate("evt_123")` → True
  - After TTL mock expiry → False again
  - Concurrent calls for same ID (asyncio tasks) → exactly one passes

- `test_solace_publisher.py` (mock `MessagingService`):
  - `publish()` calls `persistent_publisher.publish()` once on success
  - `CorrelationId` == `event_id`
  - `DMQEligible` == True on message
  - On `PubSubPlusClientException`: retries N times then logs error
  - No exception propagates to caller

- `test_handlers/`:
  - Load each fixture JSON, call handler, assert envelope schema
  - Assert `data` block contains the right normalized fields
  - Assert `raw` block equals `event.data.object`

---

## Integration Tests (tests/integration/)

Require: running Docker Compose stack (app + Solace + Redis)

- `test_webhook_endpoint.py`:
  Uses `httpx.AsyncClient` against the live FastAPI app.
  For each fixture event type:
  1. Generate a valid Stripe-signed payload using test secret
  2. POST to `/webhooks/stripe`
  3. Assert HTTP 200 returned in < 300ms
  4. Assert mock/real Solace publisher was called with correct topic
  5. Assert `stripe_webhooks_received_total` counter incremented

- `test_solace_roundtrip.py`:
  1. Call `SolacePublisher.publish(topic, payload, event_id)` directly
  2. Call `SolaceSubscriber.consume_one(queue_name, timeout=5)`
  3. Assert received payload == published payload
  4. Assert `ApplicationMessageId` == `event_id`
  5. Assert `ContentType` == `application/json`

---

## End-to-End Tests (tests/e2e/)

These are the most critical tests. They validate the **full pipeline**:
Stripe CLI trigger → HTTP webhook → bridge processing → Solace queue delivery.

Requirements: Docker Compose stack running + Stripe CLI installed + test mode keys.

### conftest_e2e.py
```python
@pytest.fixture(scope="session")
def stripe_cli():
    """
    Starts `stripe listen --forward-to http://localhost:APP_PORT/webhooks/stripe`
    as a subprocess. Captures the whsec_ signing secret from stdout.
    Updates STRIPE_WEBHOOK_SECRET env var for the app (restart or inject).
    Yields the process. Terminates on teardown.
    """

@pytest.fixture(scope="function")
async def clean_queues(solace_subscriber):
    """
    Before each test: drain all stripe.* queues to ensure clean state.
    Returns dict of {queue_name: messages_drained}.
    """

@pytest.fixture(scope="session")
async def solace_subscriber():
    """
    Authenticated SolaceSubscriber instance connected to the test broker.
    """
```

### test_e2e_pipeline.py

Test each supported event type end-to-end:

```python
@pytest.mark.parametrize("event_type,expected_queue", [
    ("payment_intent.succeeded",       "stripe.payments.inbound"),
    ("payment_intent.payment_failed",  "stripe.payments.inbound"),
    ("customer.subscription.created",  "stripe.subscriptions.inbound"),
    ("customer.subscription.updated",  "stripe.subscriptions.inbound"),
    ("customer.subscription.deleted",  "stripe.subscriptions.inbound"),
    ("invoice.payment_succeeded",      "stripe.invoices.inbound"),
    ("invoice.payment_failed",         "stripe.invoices.inbound"),
    ("customer.created",               "stripe.customers.inbound"),
    ("customer.deleted",               "stripe.customers.inbound"),
    ("charge.succeeded",               "stripe.all.inbound"),
    ("checkout.session.completed",     "stripe.all.inbound"),
])
async def test_event_flows_to_correct_queue(
    event_type, expected_queue, stripe_cli, solace_subscriber, clean_queues
):
    """
    1. Run `stripe trigger {event_type}` via subprocess
    2. Wait up to E2E_CONSUME_TIMEOUT_SECONDS for a message on expected_queue
    3. Assert message arrived (not None)
    4. Assert message['event_type'] == event_type
    5. Assert message['account_id'] is present
    6. Assert message is also present on stripe.all.inbound (catch-all)
    7. Assert message['data'] has required fields for this event type
    8. Assert message['bridge_received_at'] is a valid ISO 8601 timestamp
    9. Assert message['trace_id'] is a valid UUID4
    """
```

Additionally test:

```python
async def test_all_events_also_land_on_audit_queue(stripe_cli, solace_subscriber):
    """
    Trigger 3 different event types.
    Consume from stripe.all.inbound.
    Assert all 3 messages arrived in order.
    Assert event_types match triggers.
    """

async def test_message_user_properties(stripe_cli, solace_subscriber):
    """
    Trigger payment_intent.succeeded.
    Consume from stripe.payments.inbound with raw message access.
    Assert Solace user properties:
      - stripe_api_version is set
      - stripe_account_id matches E2E_STRIPE_ACCOUNT_ID
      - event_created_at is a Unix timestamp integer
      - bridge_received_at is a UTC ISO 8601 string
    Assert CorrelationId == event_id (evt_...)
    Assert ApplicationMessageId == event_id
    Assert ContentType == 'application/json'
    """
```

### test_e2e_idempotency.py

```python
async def test_duplicate_event_produces_one_message(
    stripe_cli, solace_subscriber, clean_queues
):
    """
    1. Load a fixture payload (payment_intent.succeeded)
    2. Sign it with the test webhook secret using stripe.WebhookSignature
    3. POST it twice to /webhooks/stripe with the SAME event.id
    4. Wait for messages on stripe.payments.inbound
    5. consume_n(queue_name, n=5, timeout=5)
    6. Assert exactly 1 message arrived (deduplication worked)
    7. Assert bridge logs show 'duplicate event skipped' for second call
    """
```

### test_e2e_dmq.py

```python
async def test_poison_message_lands_on_dmq(
    solace_subscriber, clean_queues
):
    """
    1. Manually publish a malformed JSON string directly to
       stripe/webhook/v1/payment_intent/succeeded/acct_xxx via SolacePublisher
       (bypass validation intentionally)
    2. Bind a consumer to stripe.payments.inbound that NACKS after maxRedeliveryCount
       attempts (simulate a broken downstream consumer)
    3. Assert message eventually moves to stripe.errors.dmq
    4. Consume from stripe.errors.dmq and assert it contains the original payload
    NOTE: This test requires the Solace queue maxRedeliveryCount=5 to be set by
    the provisioning script.
    """
```

### test_e2e_reconnect.py

```python
async def test_bridge_reconnects_after_broker_restart(
    docker_client, stripe_cli, solace_subscriber, clean_queues
):
    """
    1. Trigger payment_intent.succeeded, assert it arrives on queue
    2. Use docker_client (docker SDK) to restart the 'solace' container
    3. Wait for /ready to return 503 (broker offline)
    4. While offline, trigger another payment_intent.succeeded
       (the asyncio queue buffers it)
    5. Wait for /ready to return 200 again (broker reconnected)
    6. Assert the buffered event eventually arrives on the queue
    7. Assert no events were lost
    8. Assert solace_connection_status metric returns to 1
    """
```

### test_e2e_metrics.py

```python
async def test_prometheus_counters_match_triggered_events(
    stripe_cli, solace_subscriber, clean_queues
):
    """
    1. Read baseline Prometheus counters from GET /metrics
    2. Trigger 5 different event types
    3. Wait for all 5 to land on queues
    4. Re-read GET /metrics
    5. Assert stripe_webhooks_received_total increased by 5
    6. Assert stripe_events_processed_total{status='success'} increased by 5
    7. Assert solace_publish_attempts_total{status='success'} increased by >= 5
       (catch-all queue means multiple publishes per event)
    8. Assert async_queue_size == 0 (queue fully drained)
    """
```

---

## Standalone Validation Scripts

### scripts/validate_pipeline.py

A self-contained script that can be run after deployment to validate the
integration is working correctly. Zero pytest dependency.

```
Usage:
  python scripts/validate_pipeline.py \
    --app-url http://localhost:8080 \
    --stripe-key sk_test_xxx \
    --webhook-secret whsec_xxx \
    --solace-host tcp://localhost:55555 \
    --solace-vpn default \
    --solace-user stripe-bridge-user \
    --solace-password xxx \
    --account-id acct_xxx
```

The script must:
1. Print a header: "🔍 Stripe → Solace Bridge Validation"
2. Check `GET /health` → print ✅ or ❌
3. Check `GET /ready` → print ✅ or ❌ with Solace connection status
4. Run `provision_solace.py` and print queue inventory
5. For each of 5 key event types:
   a. Generate a signed Stripe test payload
   b. POST to `/webhooks/stripe`
   c. Consume from the expected queue (timeout 10s)
   d. Validate envelope schema (event_id, event_type, data keys, timestamps)
   e. Print `✅ payment_intent.succeeded → stripe.payments.inbound [32ms]`
      or `❌ invoice.payment_failed → stripe.invoices.inbound [TIMEOUT]`
6. Check Prometheus counters match expected increments
7. Print final summary:
   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Validation Results: 5/5 passed
   Total latency: avg 28ms, max 47ms
   Broker: connected | Queue depth: 0
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```
8. Exit code 0 on full pass, 1 on any failure

### scripts/consume_queue.py

A developer CLI tool:
```
Usage:
  python scripts/consume_queue.py \
    --queue stripe.payments.inbound \
    --count 10 \
    --timeout 30 \
    --pretty
```

Binds to the queue, receives N messages (or until timeout), prints formatted
JSON to stdout with timestamp, topic, and message properties. Does NOT ACK
(browse mode) unless `--ack` flag is passed.

### scripts/stripe_trigger_all.sh

Triggers every supported event type in sequence with a 1-second delay between each:
```bash
#!/bin/bash
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
```

---

## Docker & docker-compose

### docker-compose.yml (base)
Services:
1. `app` — FastAPI bridge
2. `solace` — `solace/solace-pubsub-standard:latest` (ports: 55555, 8080, 5672, 1883, 80)
3. `redis` — `redis:7-alpine`
4. `provision` — one-shot Python container that waits for Solace readiness
   (polls SEMP `GET /SEMP/v2/config/` until 200) then runs `provision_solace.py`
   with `depends_on: solace` and `restart: on-failure`

### docker-compose.e2e.yml (E2E override)
Adds:
5. `stripe-cli` — `stripe/stripe-cli:latest` container running:
   `stripe listen --forward-to http://app:8080/webhooks/stripe`
   Its stdout must be captured to extract `whsec_` signing secret.
   Use a shared volume or env-file to pass the secret to the app container.

### Dockerfile
- Multi-stage: `builder` (install deps) + `runtime` (copy app)
- Non-root user `appuser`
- `HEALTHCHECK CMD curl -f http://localhost:${APP_PORT}/ready || exit 1`
- Final image < 200MB

---

## Makefile

```makefile
.PHONY: install lint typecheck test test-unit test-integration test-e2e \
        up down provision validate logs clean

install:
	pip install -r requirements.txt -r requirements-dev.txt

lint:
	ruff check app/ tests/ scripts/

typecheck:
	mypy --strict app/

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-e2e:
	pytest tests/e2e/ -v --tb=short -s

test: test-unit test-integration

up:
	docker compose up -d --build
	@echo "Waiting for services..."
	@sleep 15
	docker compose logs provision

down:
	docker compose down -v

provision:
	python scripts/provision_solace.py

validate:
	python scripts/validate_pipeline.py \
	  --app-url http://localhost:8080 \
	  --stripe-key ${STRIPE_API_KEY} \
	  --webhook-secret ${STRIPE_WEBHOOK_SECRET} \
	  --solace-host ${SOLACE_HOST} \
	  --solace-vpn ${SOLACE_VPN} \
	  --solace-user ${SOLACE_USERNAME} \
	  --solace-password ${SOLACE_PASSWORD} \
	  --account-id ${E2E_STRIPE_ACCOUNT_ID}

e2e: up test-e2e validate

logs:
	docker compose logs -f app

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
```

---

## Helm Chart

`values.yaml` must expose:
- `replicaCount`
- `image.repository` / `image.tag`
- `config.stripe.webhookSecretRef` (K8s secret ref)
- `config.solace.host`, `vpn`, `usernameRef`, `passwordRef`
- `config.redis.enabled`, `host`
- `resources.requests/limits`
- `autoscaling.enabled`, `minReplicas`, `maxReplicas`, `targetCPU`
- `ingress.enabled`, `host`, `tls`
- `initJob.enabled` — runs provisioning script as K8s Job on deploy

---

## Quality Standards
- All code: `ruff` linting + `mypy --strict` type checking with zero errors
- Test coverage >= 85% (enforced via `pytest --cov=app --cov-fail-under=85`)
- No `print()` — `structlog` throughout
- All async code uses `async/await`; no `time.sleep()` in async context
- Every public function/class has a docstring
- Solace broker restarts handled gracefully; asyncio queue buffers in-flight events
- The full `make e2e` command must complete successfully on a clean machine
  given only a valid `.env` file with credentials

---

## README Requirements

1. Architecture diagram (Mermaid):
   ```
   Stripe → HTTPS POST → FastAPI /webhooks/stripe
      → Signature Verify → asyncio.Queue → Background Processor
      → Idempotency Check → Event Handler → SolacePublisher
      → PubSub+ Broker Topics → Durable Queues
      → (DMQ for failures)
   ```
2. Prerequisites (Docker, Python 3.11+, Stripe CLI, make)
3. Quick start: `cp .env.example .env && make e2e`
4. Full env variable reference table
5. Topic taxonomy table
6. Queue inventory table (queue name → subscribed topic → purpose)
7. Validation script usage
8. `consume_queue.py` usage examples
9. Helm deployment instructions
10. Troubleshooting (Solace connection, signature mismatch, queue backlog,
    DMQ inspection, metrics discrepancies)
