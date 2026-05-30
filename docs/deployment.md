# PulsePress Deployment / Runbook

> **Status: stub.** Walking-skeleton deploy lands in **Sprint 1**; the full
> operational runbook is completed in **Sprint 7**. Canonical sequencing is in
> `docs/sprint-plan.md`; infra decisions are in `docs/adr/` (ADR-0001, ADR-0006, ADR-0007).

This document will cover:

- Terraform layout under `infra/terraform/environments/dev` and apply/plan workflow
  (`terraform apply`/`destroy` are never run by the agent — CLAUDE.md §12).
- ECS Fargate services (API + worker), RDS, ElastiCache, S3, SQS/DLQ, EventBridge, Cognito.
- GitHub Actions CI/CD build → test → deploy pipeline.
- Scale-to-zero teardown and one-command rebuild (ADR-0007).
- Phase 1 acceptance flow verification in the deployed environment (`docs/SPEC.md` §18.1).

Until Sprint 1 there is no infrastructure to deploy.
