# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are writers and readers, and future UI decisions optimize for them first. Every authenticated user is both by default: a user is an author when they own a publication and a subscriber when they hold an active subscription.

- **Writer / Author:** creates a publication, configures subscription tiers, drafts and publishes posts, and watches subscribers, gifts and revenue with a transparent breakdown of fees and taxes.
- **Reader / Subscriber:** browses publications, subscribes free or paid, sends one-time gifts, reads posts, and follows a feed of the publications they subscribe to.
- **Admin / Operator:** the only assigned role. Views failed events, retries, amends or discards them, inspects worker attempts, and resolves reconciliation reviews.
- **Secondary audience:** recruiters and engineers evaluating PulsePress as a software engineering portfolio project. They judge it through the demo, screenshots and README. Their needs do not outrank the writer and reader experience.

## Product Purpose

PulsePress is a publication-centric publishing and subscription platform on the Substack model. Authors set their own per-publication prices, readers pay a publication directly, and the platform takes a cut of each payment.

Success for Phase 1 is a deployed end-to-end flow. A writer creates a publication and tiers and publishes a post. A second user subscribes to a paid tier. One balanced ledger transaction is recorded, the dashboard updates live, and an operator can recover a deliberately failed event.

## Positioning

Money and recovery are visible. Every payment shows its author, platform and tax split, backed by a balanced ledger. Failed event processing is recovered in the open by an operator, and every override stays on permanent record.

## Operating Context

- Writers move between drafting a post, publishing it, and watching the dashboard respond.
- Readers arrive at a publication, choose a tier or send a gift, then read posts and follow their feed.
- Operators work from a failed-event runbook and a reconciliation review, alongside CloudWatch.
- Evaluators see the product through a demo, screenshots and the README. The portfolio checklist requires screenshots of the admin recovery surface, the ledger and bill breakdown, and the SSE dashboard.

## Capabilities and Constraints

**Phase 1 scope:** Cognito auth, publications, multi-tier plans, free and paid subscriptions, one-time gifts, post lifecycle (draft, published, archived), free versus paid post visibility, newsletter-send simulation, per-reader feed, real-time creator dashboard over SSE, and the admin operability surface.

**Binding product rules:**

- All money is USD in integer cents. The bill always resolves to `author_net + platform_fee + tax = total_charged`.
- The frontend never duplicates backend domain logic. It displays the bill the API computed.
- Tiers vary price and soft benefits, not content access. Higher paid tiers are voluntary patronage and must be labeled honestly, such as "Supporter", never as more content.
- Admin recovery has exactly three verbs: retry, amend & retry, and discard. Amend is feature-flagged off by default and requires a reason and the typed confirmation `AMEND <event_id>`. Discard requires a reason of at least 10 characters.
- UI states are explicit: loading, empty, success and error.
- `docs/openapi.yaml` and `docs/SPEC.md` govern behavior and scope. See `CLAUDE.md` for the full rule set.

**Not in Phase 1:** real payments or payouts, refunds, auto-renewal, proration, multi-currency, regional tax, real email, claps, comments, bookmarks, follows, search, tags, trending, recommendations, discovery or home feed, member roles, scheduled publishing, mobile app, and chat. Newsletter sends are simulated and payments are not real, so the UI must not imply otherwise.

**Terminology:** publication, post, tier or plan, subscription, gift, bill, author net, platform fee, tax, ledger transaction, feed, failed event, reconciliation review.

## Brand Commitments

The name is PulsePress. No logo, voice guide or other brand commitment has been confirmed.

## Evidence on Hand

- **Real:** the running local system and the data it produces, the spec pack under `docs/`, and architecture diagrams under `docs/design/`.
- **Verification record:** `tasks/todo.md` records test results through Sprint 4 and states that no AWS apply was performed. Cite only what that record and later verified outcomes support.
- **Rule:** show only numbers, authors and posts produced by the running system, such as seeded demo data. Do not fabricate metrics, testimonials, customers or earnings.
- **Known violation:** `apps/web/app/page.tsx` shows invented figures ("50K+ readers", "$2M+ creator earnings") and invented authors. Remove them when that surface is next touched.
- **Absent:** real users, real revenue, testimonials and press. As of Sprint 4 the web app has no SSE dashboard or admin surface, and the repo has no load-test report.

## Product Principles

1. **Writers and readers come first.** Portfolio legibility follows from a product that works for its people, not from decorating it for reviewers.
2. **Show where the money goes.** Any surface that involves a payment makes the split and the author's net clear.
3. **Failure is part of the product.** Recovery is explicit, reasoned and on the record, with no silent fixes.
4. **Say only what is true.** Displayed numbers come from the system, and simulated behavior is not presented as real.
5. **Phase 1 is the boundary.** The default answer to a feature outside it is no.
