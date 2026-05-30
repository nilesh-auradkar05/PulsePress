# PulsePress — API Contract Summary (v1.2)

Canonical file: `docs/openapi.yaml`.

- Path entries: 21
- Operations: 29
- Schemas: 32

| Method | Path | OperationId | Tag | Idempotency-Key |
| --- | --- | --- | --- | --- |
| GET | `/me` | `getMe` | auth | no |
| GET | `/publications` | `listPublications` | publications | no |
| POST | `/publications` | `createPublication` | publications | no |
| GET | `/publications/{publication_id}` | `getPublication` | publications | no |
| PATCH | `/publications/{publication_id}` | `updatePublication` | publications | no |
| GET | `/publications/{publication_id}/summary` | `getPublicationSummary` | publications | no |
| GET | `/publications/{publication_id}/posts` | `listPosts` | posts | no |
| POST | `/publications/{publication_id}/posts` | `createPost` | posts | no |
| GET | `/posts/{post_id}` | `getPost` | posts | no |
| PATCH | `/posts/{post_id}` | `updatePost` | posts | no |
| DELETE | `/posts/{post_id}` | `archivePost` | posts | no |
| POST | `/posts/{post_id}/publish` | `publishPost` | posts | no |
| GET | `/publications/{publication_id}/plans` | `listPlans` | plans | no |
| POST | `/publications/{publication_id}/plans` | `createPlan` | plans | no |
| POST | `/subscriptions` | `createSubscription` | subscriptions | yes |
| GET | `/subscriptions/{subscription_id}` | `getSubscription` | subscriptions | no |
| PATCH | `/subscriptions/{subscription_id}` | `changeTier` | subscriptions | yes |
| DELETE | `/subscriptions/{subscription_id}` | `cancelSubscription` | subscriptions | yes |
| POST | `/gifts` | `sendGift` | gifts | yes |
| GET | `/publications/{publication_id}/events` | `listNotificationEvents` | feed | no |
| GET | `/publications/{publication_id}/events/stream` | `streamNotificationEvents` | feed | no |
| GET | `/admin/outbox-events` | `listOutboxEvents` | admin | no |
| POST | `/admin/outbox-events/{event_id}/retry` | `retryOutboxEvent` | admin | yes |
| POST | `/admin/outbox-events/{event_id}/amend` | `amendOutboxEvent` | admin | yes |
| POST | `/admin/outbox-events/{event_id}/discard` | `discardOutboxEvent` | admin | yes |
| GET | `/admin/reconciliation` | `listReconciliations` | admin | no |
| GET | `/admin/worker-attempts` | `listWorkerAttempts` | admin | no |
| GET | `/feed/events` | `listUserFeedEvents` | feed | no |
| GET | `/feed/events/stream` | `streamUserFeedEvents` | feed | no |
