# PulsePress Observability

> **Status: stub.** Named CloudWatch alarms and the operability dashboard are
> defined in **Sprint 6**. The canonical observability rules are in `CLAUDE.md` §13
> and `docs/architecture.md`; this doc collects the operator-facing view.

This document will cover:

- Structured JSON log fields: `request_id`, `correlation_id`, `user_id`, `event_id`,
  `event_type`, `route`, `status_code`.
- OpenTelemetry/ADOT instrumentation across the API and worker paths.
- Required metrics: API request count, p50/p95 latency, error rate; SQS queue depth and
  `sqs_age_of_oldest_message`; DLQ depth; `worker_handler_failures_total`,
  `worker_handler_duration_p95`; outbox pending count and oldest-pending age; Redis hit/miss.
- The named CloudWatch alarms (Sprint 6) and where their screenshots live for the portfolio.

Until Sprint 6 this is a placeholder; metric/alarm names trace to `CLAUDE.md` §13.
