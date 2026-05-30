# Design Markdown Companions

These files are the AI-readable companions for the HTML diagrams in `docs/design/`.

Use these files for Claude Code/Codex task tracing because Markdown is compact, diffable, and semantically explicit. Use the HTML files for screenshots, README embeds, and human review.

Source-of-truth order:

1. `docs/openapi.yaml` for HTTP behavior.
2. `docs/event-catalog.md` for event payloads and handler invariants.
3. `docs/architecture.md` for architecture and data model.
4. `docs/sprint-plan.md` for execution.
5. `docs/test-plan.md` for verification.
6. `docs/design-md/*.md` for diagram summaries.
7. `docs/design/*.html` for visual presentation.
