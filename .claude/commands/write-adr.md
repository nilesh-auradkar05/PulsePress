---
description: Scaffold a new Architecture Decision Record
argument-hint: "<short decision title>"
---

Create a new ADR for: **$ARGUMENTS**.

1. Look at the existing ADRs in `docs/adr/` to match their exact format and to pick the
   next sequential number (`ADR-00NN`).
2. Create `docs/adr/ADR-00NN-<kebab-title>.md` following the same structure as the existing
   files (Status, Context, Decision, Consequences, and any sections the others use).
3. Set Status to `Proposed` until the decision is accepted.
4. If this decision changes an existing rule, note which ADR/section it supersedes and update
   the `docs/SPEC.md` §17 ADR table.
5. Keep it to one decision. Do not implement the decision's code here — an ADR records intent.

Stop after writing the ADR and summarize the decision for review.
