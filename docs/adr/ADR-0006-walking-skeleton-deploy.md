# ADR-0006-walking-skeleton-deploy — Walking-skeleton deploy

Status: Accepted for Phase 1.

## Context

Cloud deployment is the highest-risk, least-reversible part of the project: IAM, VPC
networking, image build/push, ALB target wiring, and Fargate task placement all have to be
correct together before anything serves traffic. Discovering those issues *after* building the
full feature set would conflate application bugs with infrastructure bugs.

The walking-skeleton strategy de-risks this by deploying the smallest possible end-to-end slice
first — at the end of Sprint 1, before any feature code — so the deployment path is proven on a
trivial surface and later sprints add resources to a base that already works.

## Decision

The Sprint 1 deployable is a FastAPI app exposing a single internal endpoint, `GET /healthz`
(static JSON: service, version, status; no auth). It is deliberately **not** part of the product
OpenAPI contract — it is an operational ALB health-check target.

Terraform (`infra/terraform`) provisions the cost-minimal foundation:

- **network** — VPC, two public + two private subnets across two AZs, an internet gateway, public
  route tables. **No NAT gateway**; private subnets are reserved for Sprint 2's RDS/Redis.
- **ecr** — repositories for the `api` and `worker` images.
- **alb** — internet-facing ALB, **HTTP:80 only**, target group health-checking `/healthz`.
- **ecs** — cluster, API task definition + Fargate service running in **public subnets with a
  public IP** (so it pulls images from ECR over the IGW with no NAT), least-privilege service
  security group (ingress from the ALB SG only), task/execution IAM roles, and a CloudWatch log group.

Scope guards for this sprint:

- **Build-only.** `terraform apply` is a separate, explicitly-approved human step (CLAUDE.md §12);
  CI verifies `fmt`/`validate` and never applies.
- **API only.** The worker has an ECR repo but no ECS service yet (it gains one in Sprint 4 when it
  has work to do). The web app is not deployed.
- Service `desired_count` is a variable so the service can be scaled to zero (ADR-0007).

## Consequences

- **+** The first deploy is tiny and debuggable; infrastructure correctness is proven before
  feature code, and later sprints extend a known-good base.
- **+** No NAT gateway, HTTP-only, and `containerInsights` disabled keep cost-at-rest near zero.
- **−** Tasks run in public subnets with public IPs. Mitigated: the service security group accepts
  ingress only from the ALB security group. When private data services (RDS/Redis) arrive in
  Sprint 2 they go in the private subnets, and NAT vs. VPC endpoints is revisited then.
- **−** HTTP-only is unsuitable for real auth traffic; TLS/ACM + a domain are added before product
  endpoints are exposed.
- The `/healthz` endpoint lives outside `docs/openapi.yaml` by design; see tasks/lessons.md
  (2026-05-30) for the reconciliation with CLAUDE.md §20.
