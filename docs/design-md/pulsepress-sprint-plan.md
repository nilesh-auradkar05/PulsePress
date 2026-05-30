# PulsePress — Sprint Plan Summary (v1.2)

See canonical `docs/sprint-plan.md`.

| Sprint | Goal | Key work | Guardrail |
| --- | --- | --- | --- |
| 0 | Guardrails | Commit spec pack, CLAUDE, ADR stubs, hooks, task board | No app code |
| 1 | Foundation + walking deploy | Local stack + health-only API deployed to ECS Fargate behind ALB | De-risk cloud first |
| 2 | Schema + auth | 17-table Alembic schema, Cognito/JWT, /me, RDS, ElastiCache | Earn API right |
| 3 | Commerce API + outbox | Publications/plans/subscriptions/gifts/idempotency/outbox/bill breakdown | Atomic writes |
| 4 | Worker + ledger | Outbox poller, EventBridge→SQS→worker, ledger_transactions + entries, receipts, DLQ | Async backbone |
| 5 | Publishing + newsletter + SSE | Post CRUD, publish event-door, newsletter artifact, user feed, Redis/SSE | Content + realtime |
| 6 | Operability | CloudWatch alarms, admin retry/amend/discard, reconciliation, chaos scripts | Recoverability |
| 7 | Hardening + load | k6, p95 capture, DB tuning, failure-mode evidence, cost/teardown | Reviewer-proofing |
| 8 | Polish + portfolio | README, diagrams, demo, phase gates, resume bullets, fresh clone test | Make it legible |
