# PulsePress — High-Level Architecture (v1.2)

Canonical companion for `docs/design/pulsepress-hld-architecture.html`.

## Core flow

`Frontend → ALB → API → PostgreSQL(outbox) → Outbox poller → EventBridge → SQS/DLQ → Worker → PostgreSQL/S3/Redis → SSE/feed UI`.

## Settled decisions

- Substack-style publication-centric product.
- FastAPI API and Python worker run on ECS Fargate.
- PostgreSQL/RDS is the source of truth.
- Redis/ElastiCache is cache + pub/sub fanout only.
- EventBridge + SQS provide the async backbone.
- S3 stores newsletter and receipt artifacts.
- Cognito handles OAuth2/OIDC Authorization Code + PKCE.
- CloudWatch + OpenTelemetry provide traces, metrics, alarms.

## v1.2 changes reflected

- Review-era wording and open product identity ambiguity removed.
- The domain is PulsePress only; legacy naming/tipping split removed.
- Worker writes receipts/newsletters; API does not write S3 artifacts for commerce receipts.
- Ledger model is `ledger_transactions` + `ledger_entries`, not a cross-row CHECK on `ledger_entries`.
- Reader feed is durable through `user_feed_events`, then pushed over SSE.
