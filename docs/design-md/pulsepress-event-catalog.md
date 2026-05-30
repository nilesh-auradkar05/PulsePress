# PulsePress — Event Catalog Summary (v1.2)

See canonical `docs/event-catalog.md`.

| Event | Context | Producer | Trigger | Notes |
| --- | --- | --- | --- | --- |
| `post.published` | publishing | API | publishPost | post_versions snapshot id; no body |
| `newsletter.send.requested` | publishing | worker | post.published handler | recipient_user_ids snapshot |
| `newsletter.sent` | publishing | worker | newsletter send simulation | artifact_s3_key + recipient_count_sim |
| `newsletter.send.failed` | publishing | worker | S3/render/fanout failure | failure reason; drives ops |
| `subscription.created` | commerce | API | createSubscription | bill breakdown; free still idempotent but no ledger |
| `subscription.tier_changed` | commerce | API | changeTier | immediate update; no ledger in P1 |
| `subscription.canceled` | commerce | API | cancelSubscription | access retained until period_end |
| `gift.sent` | commerce | API | sendGift | bill breakdown for gift amount |
| `ledger.transaction.recorded` | kernel | worker | paid subscription/gift processed | one per balanced transaction, not per row |
| `event.processing.failed` | kernel | worker | handler failure or DLQ signal | feeds admin operability |
