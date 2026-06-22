"""Service/domain layer: commerce business logic, idempotency, outbox.

Per CLAUDE.md §9, money-shaped business logic lives here, not in route handlers.
Routes stay thin: validate input, call a service, translate domain errors to
RFC 7807.
"""
