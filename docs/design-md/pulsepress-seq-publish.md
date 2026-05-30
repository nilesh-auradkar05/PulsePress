# PulsePress — Publish → Newsletter Sequence (v1.2)

1. Writer sends `POST /v1/posts/{post_id}/publish` without `Idempotency-Key`.
2. API validates JWT, owner authorization, draft status, non-empty title/body.
3. Same DB transaction updates `posts`, inserts immutable `post_versions`, and inserts `outbox_events(post.published)`.
4. API returns published state and `version_id`.
5. Outbox poller publishes event.
6. Worker handles `post.published`, fetches content from `post_versions`, snapshots recipients.
7. Recipient rule: free posts go to all active subscribers; paid posts go to active paid subscribers, including canceled-but-still-access-valid subscriptions.
8. Worker emits `newsletter.send.requested` with recipient ids.
9. Worker renders simulated newsletter, stores artifact in S3, writes `newsletter_sends`.
10. Worker writes `notification_events` and `user_feed_events`, publishes Redis/SSE notifications.
11. Worker emits `newsletter.sent`, or `newsletter.send.failed` on durable failure.
