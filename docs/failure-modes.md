# PulsePress Failure Modes

Canonical failure evidence should be filled during Sprint 7.

Required documented cases:

1. Duplicate purchase request.
2. Same idempotency key with different body.
3. Worker crash after partial processing.
4. EventBridge publish failure.
5. SQS redelivery.
6. Redis unavailable during SSE.
7. S3 write failure for newsletter/receipt artifact.
8. Invalid/expired JWT.
9. Subscriber cancels mid-newsletter fanout.
10. Writer edits post mid-fanout.
11. Poison event reaches DLQ/admin surface.

For each case record:

- How to inject.
- Expected system behavior.
- Observed behavior.
- Logs/traces/screenshots.
- Recovery path.
