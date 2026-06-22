# PulsePress AWS Production Setup and Test Walkthrough

This guide describes the production-shaped AWS setup for PulsePress: credentials,
permissions, Terraform, ECR image push, RDS/Secrets Manager wiring, ECS
migrations, worker delivery verification, Cognito test tokens, API smoke tests,
and current web acceptance boundaries.

Current repo reality: `infra/terraform/environments/dev` exists; a dedicated
`infra/terraform/environments/prod` directory does not yet exist. Create it
explicitly before a production-shaped deploy. Do not reuse the dev environment
as a production substitute.

## 1. What Gets Deployed

The current Terraform modules create:

- VPC with public/private subnets.
- ALB for the API.
- ECR repositories for API and worker images.
- ECS Fargate cluster, separate API and worker task definitions/services, scoped
  task and execution roles, and CloudWatch log groups.
- Private encrypted RDS PostgreSQL with AWS-managed master password.
- Private ElastiCache Redis.
- Cognito user pool, public app client, and hosted UI domain.
- Secrets Manager secret for `PULSEPRESS_DATABASE_URL`.
- EventBridge bus, worker SQS queue, worker poison-message DLQ, distinct
  EventBridge target-delivery DLQ, and a private versioned receipt bucket.

Current application boundary:

- API production auth validates Cognito JWTs.
- Web local auth is passwordless and development-only.
- A production browser PKCE callback is not implemented in the current web app.
  This guide includes manual Cognito PKCE token acquisition for API smoke tests.
  Do not mark full production browser acceptance complete until the web PKCE
  adapter/callback is implemented and configured.

## 2. Required Keys, Tokens, and Secrets

You need these credentials or secrets:

| Item | Used by | How to get it | Store where |
| --- | --- | --- | --- |
| AWS CLI temporary credentials | Terraform, AWS CLI, Docker ECR login | IAM Identity Center with `aws configure sso` and `aws sso login` | AWS CLI cache only |
| ECR registry token | `docker login` | `aws ecr get-login-password` | Docker credential store/cache |
| Terraform state access | Terraform | S3 backend bucket permissions, or local state for temporary solo demos only | S3 backend recommended |
| RDS master password | RDS admin connection string composition | RDS-managed Secrets Manager secret | AWS-managed secret |
| Application database URL | ECS API task | Compose from RDS endpoint + RDS master secret | `pulsepress-prod/database-url` in Secrets Manager |
| Worker bus/queue/bucket values | ECS worker task | Terraform outputs | ECS environment only |
| Cognito test user password | Manual hosted-UI sign-in | `admin-create-user` + `admin-set-user-password` | Local password manager, never git |
| Cognito ID token | API smoke tests | Hosted UI authorization-code + PKCE flow | Shell variable only |

Do not create long-lived IAM user access keys for normal deployment. Use IAM
Identity Center temporary credentials unless your organization has a different
approved broker.

## 3. Required AWS Permissions

For a solo portfolio account, the practical bootstrap path is an IAM Identity
Center permission set with `AdministratorAccess`, then tighten later. For a
shared or employer-controlled account, request a custom deployer permission set
that can manage these services:

- `sts:GetCallerIdentity`
- IAM role/policy operations needed by Terraform, including `iam:CreateRole`,
  `iam:DeleteRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`,
  `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRole`, `iam:PassRole`
- EC2 networking and security groups: `ec2:*Vpc*`, `ec2:*Subnet*`,
  `ec2:*Route*`, `ec2:*InternetGateway*`, `ec2:*SecurityGroup*`,
  `ec2:Describe*`, `ec2:CreateTags`, `ec2:DeleteTags`
- ALB: `elasticloadbalancing:*`
- ECS: `ecs:*`
- ECR: `ecr:*`
- RDS: `rds:*`
- ElastiCache: `elasticache:*`
- Cognito: `cognito-idp:*`
- Secrets Manager: `secretsmanager:*`
- CloudWatch Logs: `logs:*`
- CloudWatch metrics/alarms if later modules add them: `cloudwatch:*`
- EventBridge, SQS, and S3 operations used by Terraform: `events:*`, `sqs:*`,
  and `s3:*` scoped to the deployment account during bootstrap
- KMS read/use permissions for AWS-managed keys, and customer-managed key
  permissions if you choose customer-managed encryption
- S3 state backend permissions if using S3 remote state:
  `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, and lockfile
  `s3:DeleteObject` on the state lock object

RDS-managed master credentials require permissions to create and tag Secrets
Manager secrets and to describe the KMS key used by Secrets Manager.

## 4. Acquire AWS CLI Access

### 4.1 New Solo AWS Account

1. Create or sign in to the AWS account root user.
2. Enable MFA on the root user.
3. Do not use root for deployment.
4. Open IAM Identity Center.
5. Enable IAM Identity Center for the account or organization.
6. Create a user for yourself.
7. Create a permission set for deployment. For the first solo bootstrap,
   `AdministratorAccess` is acceptable; for shared accounts, use the custom
   deployer permissions listed above.
8. Assign the permission set to your AWS account and user.
9. Copy the AWS access portal start URL.

### 4.2 Existing Organization Account

Ask the AWS administrator for:

- AWS account ID.
- AWS region approved for this deploy.
- IAM Identity Center start URL.
- Permission set name.
- Confirmation that the permission set includes the deployer permissions above.
- Approval to create externally reachable ALB, ECS, RDS, ElastiCache, ECR,
  Cognito, CloudWatch Logs, EventBridge, SQS, S3, and Secrets Manager resources.

### 4.3 Configure AWS CLI SSO

```bash
aws configure sso
```

Use these values when prompted:

- SSO session name: `pulsepress`
- SSO start URL: your AWS access portal URL
- SSO region: the IAM Identity Center region
- CLI default client region: deployment region, for example `us-east-1`
- CLI profile name: `pulsepress-prod`

Log in and verify the caller:

```bash
export AWS_PROFILE=pulsepress-prod
export AWS_REGION=us-east-1

aws sso login --profile "$AWS_PROFILE"
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

Expected output: the target account ID and an assumed-role ARN from IAM Identity
Center.

## 5. Local Tooling

Install and verify:

```bash
aws --version
docker --version
terraform version
jq --version
python3 --version
uv --version
pnpm --version
```

Set common variables:

```bash
export AWS_PROFILE=pulsepress-prod
export AWS_REGION=us-east-1
export PROJECT=pulsepress
export ENVIRONMENT=prod
export TF_ENV_DIR=infra/terraform/environments/prod
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export IMAGE_TAG=$(git rev-parse --short HEAD)
```

## 6. Create the Production Terraform Environment

Create the prod environment from the current dev environment:

```bash
mkdir -p "$TF_ENV_DIR"
cp infra/terraform/environments/dev/main.tf "$TF_ENV_DIR/main.tf"
cp infra/terraform/environments/dev/variables.tf "$TF_ENV_DIR/variables.tf"
cp infra/terraform/environments/dev/outputs.tf "$TF_ENV_DIR/outputs.tf"
cp infra/terraform/environments/dev/providers.tf "$TF_ENV_DIR/providers.tf"
cp infra/terraform/environments/dev/versions.tf "$TF_ENV_DIR/versions.tf"
cp infra/terraform/environments/dev/backend.tf "$TF_ENV_DIR/backend.tf"
cp infra/terraform/environments/dev/terraform.tfvars.example "$TF_ENV_DIR/terraform.tfvars"
```

Edit `terraform.tfvars`:

```hcl
aws_region             = "us-east-1"
project                = "pulsepress"
environment            = "prod"
api_image_tag          = "bootstrap"
worker_image_tag       = "bootstrap"
api_desired_count      = 0
worker_desired_count   = 0
cognito_domain_prefix  = "pulsepress-prod-<unique-suffix>"
```

Use both desired counts at zero for the first apply. This lets Terraform create
ECR, RDS, Cognito, Secrets Manager, EventBridge, SQS, S3, and ECS before images,
the database secret, and migrations exist.

## 7. Terraform State

Temporary solo demo: local state is acceptable if the repo remains private and
only one operator runs Terraform.

Production-shaped or shared demo: use an S3 backend with state locking.

Create a backend bucket:

```bash
export TF_STATE_BUCKET="pulsepress-prod-tfstate-${AWS_ACCOUNT_ID}-${AWS_REGION}"

aws s3api create-bucket \
  --bucket "$TF_STATE_BUCKET" \
  --region "$AWS_REGION"

aws s3api put-bucket-versioning \
  --bucket "$TF_STATE_BUCKET" \
  --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
  --bucket "$TF_STATE_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

For regions other than `us-east-1`, add
`--create-bucket-configuration LocationConstraint=$AWS_REGION` to
`create-bucket`.

Edit `infra/terraform/environments/prod/backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket       = "pulsepress-prod-tfstate-<account-id>-us-east-1"
    key          = "pulsepress/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

## 8. Bootstrap AWS Resources

Initialize and validate:

```bash
terraform -chdir="$TF_ENV_DIR" init
terraform -chdir="$TF_ENV_DIR" fmt -check -recursive
terraform -chdir="$TF_ENV_DIR" validate
terraform -chdir="$TF_ENV_DIR" plan -out=tfplan
```

Review the plan carefully. Apply only after approval:

```bash
terraform -chdir="$TF_ENV_DIR" apply tfplan
```

Expected result:

- ECR repositories exist.
- RDS and ElastiCache are private.
- Cognito user pool/client/domain exist.
- API and worker ECS services exist with desired count 0.
- EventBridge, both DLQs, the primary worker queue, and the receipt bucket exist.
- App DB URL secret exists but has no useful value yet.

Capture outputs:

```bash
ALB_DNS=$(terraform -chdir="$TF_ENV_DIR" output -raw alb_dns_name)
ECR_API_URL=$(terraform -chdir="$TF_ENV_DIR" output -json ecr_repository_urls | jq -r '.["pulsepress-api"]')
ECR_WORKER_URL=$(terraform -chdir="$TF_ENV_DIR" output -json ecr_repository_urls | jq -r '.["pulsepress-worker"]')
ECS_CLUSTER=$(terraform -chdir="$TF_ENV_DIR" output -raw ecs_cluster_name)
WORKER_SERVICE=$(terraform -chdir="$TF_ENV_DIR" output -raw worker_service_name)
WORKER_QUEUE_URL=$(terraform -chdir="$TF_ENV_DIR" output -raw worker_queue_url)
WORKER_DLQ_URL=$(terraform -chdir="$TF_ENV_DIR" output -raw worker_dead_letter_queue_url)
EVENT_DELIVERY_DLQ_URL=$(terraform -chdir="$TF_ENV_DIR" output -raw event_delivery_dead_letter_queue_url)
RECEIPT_BUCKET=$(terraform -chdir="$TF_ENV_DIR" output -raw receipt_bucket_name)
EVENT_BUS_NAME=$(terraform -chdir="$TF_ENV_DIR" output -raw event_bus_name)
RDS_ENDPOINT=$(terraform -chdir="$TF_ENV_DIR" output -raw rds_endpoint)
COGNITO_ISSUER=$(terraform -chdir="$TF_ENV_DIR" output -raw cognito_issuer)
COGNITO_CLIENT_ID=$(terraform -chdir="$TF_ENV_DIR" output -raw cognito_client_id)
ECS_SERVICE="${PROJECT}-${ENVIRONMENT}-api"
```

## 9. Build and Push the API and Worker Images

Authenticate Docker to ECR:

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
  "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

Build and push:

```bash
docker build -t pulsepress-api:"$IMAGE_TAG" apps/api
docker tag pulsepress-api:"$IMAGE_TAG" "$ECR_API_URL:$IMAGE_TAG"
docker push "$ECR_API_URL:$IMAGE_TAG"

docker build -t pulsepress-worker:"$IMAGE_TAG" apps/worker
docker tag pulsepress-worker:"$IMAGE_TAG" "$ECR_WORKER_URL:$IMAGE_TAG"
docker push "$ECR_WORKER_URL:$IMAGE_TAG"
```

Update `terraform.tfvars`:

```hcl
api_image_tag       = "<IMAGE_TAG>"
worker_image_tag    = "<IMAGE_TAG>"
api_desired_count   = 0
worker_desired_count = 0
```

Keep both desired counts at 0 until the database URL secret is populated and
Alembic has completed.

## 10. Connect RDS to the API Secret

Get the RDS-managed master credential secret:

```bash
RDS_INSTANCE_ID="${PROJECT}-${ENVIRONMENT}-pg"
RDS_SECRET_ARN=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_INSTANCE_ID" \
  --query "DBInstances[0].MasterUserSecret.SecretArn" \
  --output text)
```

Get the application database URL secret:

```bash
APP_DB_SECRET_NAME="${PROJECT}-${ENVIRONMENT}/database-url"
APP_DB_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "$APP_DB_SECRET_NAME" \
  --query ARN \
  --output text)
```

Read the RDS credentials into local shell variables:

```bash
RDS_CREDS=$(aws secretsmanager get-secret-value \
  --secret-id "$RDS_SECRET_ARN" \
  --query SecretString \
  --output text)

DB_USER=$(printf '%s' "$RDS_CREDS" | jq -r '.username')
DB_PASS=$(printf '%s' "$RDS_CREDS" | jq -r '.password')
DB_NAME=pulsepress
```

Compose the SQLAlchemy URL with URL-encoded credentials:

```bash
DATABASE_URL=$(DB_USER="$DB_USER" DB_PASS="$DB_PASS" RDS_ENDPOINT="$RDS_ENDPOINT" DB_NAME="$DB_NAME" python3 - <<'PY'
import os
from urllib.parse import quote

user = quote(os.environ["DB_USER"], safe="")
password = quote(os.environ["DB_PASS"], safe="")
host = os.environ["RDS_ENDPOINT"]
name = os.environ["DB_NAME"]
print(f"postgresql+psycopg://{user}:{password}@{host}:5432/{name}")
PY
)
```

Store it in Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id "$APP_DB_SECRET_ARN" \
  --secret-string "$DATABASE_URL"
```

Do not echo `DATABASE_URL` into logs or commit it.

## 11. Deploy Task Definitions with Services Stopped

Update `terraform.tfvars`:

```hcl
api_image_tag       = "<IMAGE_TAG>"
worker_image_tag    = "<IMAGE_TAG>"
api_desired_count   = 0
worker_desired_count = 0
```

Plan and apply:

```bash
terraform -chdir="$TF_ENV_DIR" plan -out=tfplan
terraform -chdir="$TF_ENV_DIR" apply tfplan
```

The apply registers the API and worker task definitions without processing
events. Capture the API task definition and network settings for the one-off
migration task:

```bash
TASK_DEF=$(aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --query "services[0].taskDefinition" \
  --output text)

NETWORK_JSON=$(aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --query "services[0].networkConfiguration.awsvpcConfiguration" \
  --output json)

SUBNETS=$(printf '%s' "$NETWORK_JSON" | jq -r '.subnets | @csv')
SECURITY_GROUPS=$(printf '%s' "$NETWORK_JSON" | jq -r '.securityGroups | @csv')
ASSIGN_PUBLIC_IP=$(printf '%s' "$NETWORK_JSON" | jq -r '.assignPublicIp')
```

## 12. Run Alembic on ECS

Run migrations:

```bash
MIGRATION_TASK_ARN=$(aws ecs run-task \
  --cluster "$ECS_CLUSTER" \
  --launch-type FARGATE \
  --task-definition "$TASK_DEF" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUPS],assignPublicIp=$ASSIGN_PUBLIC_IP}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["uv","run","--no-dev","alembic","upgrade","head"]}]}' \
  --query "tasks[0].taskArn" \
  --output text)

aws ecs wait tasks-stopped --cluster "$ECS_CLUSTER" --tasks "$MIGRATION_TASK_ARN"

aws ecs describe-tasks \
  --cluster "$ECS_CLUSTER" \
  --tasks "$MIGRATION_TASK_ARN" \
  --query "tasks[0].containers[0].exitCode"
```

Expected output: `0`.

## 13. Start API and Worker Services

Update `terraform.tfvars` only after the migration exits successfully:

```hcl
api_desired_count    = 1
worker_desired_count = 1
```

Apply and wait for both services:

```bash
terraform -chdir="$TF_ENV_DIR" plan -out=tfplan
terraform -chdir="$TF_ENV_DIR" apply tfplan

aws ecs wait services-stable \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" "$WORKER_SERVICE"
```

If a service does not stabilize, inspect its events and logs:

```bash
aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" "$WORKER_SERVICE" \
  --query "services[].events[0:10].[createdAt,message]" \
  --output table

aws logs tail "/ecs/${PROJECT}-${ENVIRONMENT}-worker" --since 10m
```

The worker task role is deliberately limited to `events:PutEvents` on the
project bus, consume/delete operations on the primary worker queue, and
`s3:GetObject`/`s3:PutObject` under `receipts/*`. It has no receipt delete or
DLQ-consume permission.

## 14. Create a Cognito Demo User

Get the user pool ID:

```bash
USER_POOL_ID=$(aws cognito-idp list-user-pools \
  --max-results 60 \
  --query "UserPools[?Name=='${PROJECT}-${ENVIRONMENT}-users'].Id | [0]" \
  --output text)
```

Create permanent-password demo users:

```bash
DEMO_EMAIL=demo@example.com
DEMO_PASSWORD="DemoPassword$(openssl rand -hex 8)Aa1"
READER_EMAIL=reader@example.com
READER_PASSWORD="ReaderPassword$(openssl rand -hex 8)Aa1"

aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$DEMO_EMAIL" \
  --user-attributes Name=email,Value="$DEMO_EMAIL" Name=email_verified,Value=true Name=name,Value="Demo Writer" \
  --temporary-password "$DEMO_PASSWORD" \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "$DEMO_EMAIL" \
  --password "$DEMO_PASSWORD" \
  --permanent

aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$READER_EMAIL" \
  --user-attributes Name=email,Value="$READER_EMAIL" Name=email_verified,Value=true Name=name,Value="Demo Reader" \
  --temporary-password "$READER_PASSWORD" \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id "$USER_POOL_ID" \
  --username "$READER_EMAIL" \
  --password "$READER_PASSWORD" \
  --permanent
```

Store `DEMO_PASSWORD` and `READER_PASSWORD` in a local password manager if you
need browser testing. Do not commit them.

Capture the Cognito `sub`:

```bash
DEMO_SUB=$(aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$DEMO_EMAIL" \
  --query "UserAttributes[?Name=='sub'].Value | [0]" \
  --output text)

READER_SUB=$(aws cognito-idp admin-get-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$READER_EMAIL" \
  --query "UserAttributes[?Name=='sub'].Value | [0]" \
  --output text)
```

## 15. Seed Demo Content on ECS

Run the seed command as a one-off ECS task:

```bash
SEED_OVERRIDES=$(jq -cn \
  --arg sub "$DEMO_SUB" \
  --arg email "$DEMO_EMAIL" \
  '{"containerOverrides":[{"name":"api","command":["uv","run","--no-dev","python","-m","app.scripts.seed_demo_content","--owner-sub",$sub,"--owner-email",$email,"--owner-name","Demo Writer"]}]}')

SEED_TASK_ARN=$(aws ecs run-task \
  --cluster "$ECS_CLUSTER" \
  --launch-type FARGATE \
  --task-definition "$TASK_DEF" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUPS],assignPublicIp=$ASSIGN_PUBLIC_IP}" \
  --overrides "$SEED_OVERRIDES" \
  --query "tasks[0].taskArn" \
  --output text)

aws ecs wait tasks-stopped --cluster "$ECS_CLUSTER" --tasks "$SEED_TASK_ARN"

aws ecs describe-tasks \
  --cluster "$ECS_CLUSTER" \
  --tasks "$SEED_TASK_ARN" \
  --query "tasks[0].containers[0].exitCode"
```

Expected output: `0`. Running the same task again must reuse existing seed rows
and create no duplicates.

## 16. Get a Cognito ID Token Manually

This manual PKCE flow is for API smoke tests until the web app has a production
PKCE callback.

Set the hosted UI host and redirect URI:

```bash
COGNITO_DOMAIN_PREFIX="${PROJECT}-${ENVIRONMENT}-auth-<same-unique-suffix-used-in-tfvars>"
COGNITO_HOST="${COGNITO_DOMAIN_PREFIX}.auth.${AWS_REGION}.amazoncognito.com"
REDIRECT_URI="http://localhost:3000/auth/callback"
```

Generate a PKCE verifier/challenge:

```bash
CODE_VERIFIER=$(openssl rand -base64 96 | tr -d '\n' | tr '+/' '-_' | tr -d '=' | cut -c1-96)
CODE_CHALLENGE=$(printf '%s' "$CODE_VERIFIER" | openssl dgst -sha256 -binary | openssl base64 | tr '+/' '-_' | tr -d '=')
STATE=$(openssl rand -hex 16)
```

Build the hosted UI URL:

```bash
AUTH_URL=$(COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" REDIRECT_URI="$REDIRECT_URI" CODE_CHALLENGE="$CODE_CHALLENGE" STATE="$STATE" COGNITO_HOST="$COGNITO_HOST" python3 - <<'PY'
import os
from urllib.parse import urlencode

query = urlencode({
    "client_id": os.environ["COGNITO_CLIENT_ID"],
    "response_type": "code",
    "scope": "openid email profile",
    "redirect_uri": os.environ["REDIRECT_URI"],
    "code_challenge": os.environ["CODE_CHALLENGE"],
    "code_challenge_method": "S256",
    "state": os.environ["STATE"],
})
print(f"https://{os.environ['COGNITO_HOST']}/oauth2/authorize?{query}")
PY
)

printf '%s\n' "$AUTH_URL"
```

Open the URL, sign in as `demo@example.com`, and copy the `code` query
parameter from the redirected URL. For reader commerce tests, repeat this
section as `reader@example.com` and store that result as `READER_ID_TOKEN`.
The local app may show a 404 because the callback route is not implemented yet;
the browser address still contains the authorization code.

Exchange the code:

```bash
export AUTH_CODE="<code-from-browser-url>"

TOKEN_JSON=$(curl -fsS -X POST "https://${COGNITO_HOST}/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=authorization_code" \
  --data-urlencode "client_id=${COGNITO_CLIENT_ID}" \
  --data-urlencode "code=${AUTH_CODE}" \
  --data-urlencode "redirect_uri=${REDIRECT_URI}" \
  --data-urlencode "code_verifier=${CODE_VERIFIER}")

ID_TOKEN=$(printf '%s' "$TOKEN_JSON" | jq -r '.id_token')
```

Expected output: `ID_TOKEN` is a non-empty JWT.

## 17. AWS API Smoke Tests

Check health:

```bash
curl -fsS "http://${ALB_DNS}/healthz"
```

Expected output includes:

```json
{"status":"ok"}
```

Verify Cognito-backed auth:

```bash
curl -fsS "http://${ALB_DNS}/v1/me" \
  -H "Authorization: Bearer $ID_TOKEN"
```

Expected output: the `demo@example.com` user.

Verify owner-scoped publications:

```bash
curl -fsS "http://${ALB_DNS}/v1/publications?owner=me" \
  -H "Authorization: Bearer $ID_TOKEN"
```

Expected output: seeded publications owned by the demo user's Cognito `sub`.

Create a publication:

```bash
PUB_ID=$(curl -fsS -X POST "http://${ALB_DNS}/v1/publications" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"handle":"aws-smoke-notes","name":"AWS Smoke Notes","description":"Production smoke test"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
```

Create, edit, publish, read, and archive a post:

```bash
POST_ID=$(curl -fsS -X POST "http://${ALB_DNS}/v1/publications/${PUB_ID}/posts" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"AWS smoke post","body":"This verifies production-shaped CRUD.","visibility":"free"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -fsS -X PATCH "http://${ALB_DNS}/v1/posts/${POST_ID}" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"AWS smoke post edited"}'

curl -fsS -X POST "http://${ALB_DNS}/v1/posts/${POST_ID}/publish" \
  -H "Authorization: Bearer $ID_TOKEN"

curl -fsS "http://${ALB_DNS}/v1/posts/${POST_ID}" \
  -H "Authorization: Bearer $ID_TOKEN"

curl -fsS -X DELETE "http://${ALB_DNS}/v1/posts/${POST_ID}" \
  -H "Authorization: Bearer $ID_TOKEN"
```

Expected result:

- Create returns 201.
- Edit returns 200.
- Publish returns `newsletter_status=queued` on first call.
- A second publish returns `newsletter_status=already_processed`.
- Read returns the post body for the owner.
- Archive returns status `archived`.

Verify Sprint-3 commerce and paid-post entitlement. This requires the reader ID
token from the repeated PKCE flow described above:

```bash
export READER_ID_TOKEN="<reader-id-token>"
newkey() { python3 -c "import uuid;print(uuid.uuid4().hex)"; }

PAID_PLAN=$(curl -fsS -X POST "http://${ALB_DNS}/v1/publications/${PUB_ID}/plans" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Supporter","monthly_price_cents":500,"allow_open_amount":true}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

PAID_POST=$(curl -fsS -X POST "http://${ALB_DNS}/v1/publications/${PUB_ID}/posts" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"AWS paid smoke","body":"Paid subscriber body.","visibility":"paid"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -fsS -X POST "http://${ALB_DNS}/v1/posts/${PAID_POST}/publish" \
  -H "Authorization: Bearer $ID_TOKEN"

curl -fsS -X POST "http://${ALB_DNS}/v1/subscriptions" \
  -H "Authorization: Bearer $READER_ID_TOKEN" \
  -H "Idempotency-Key: $(newkey)" \
  -H "Content-Type: application/json" \
  -d "{\"publication_id\":\"$PUB_ID\",\"plan_id\":\"$PAID_PLAN\",\"amount_cents\":500}" \
  | jq '{status,tier,bill}'

curl -fsS "http://${ALB_DNS}/v1/posts/${PAID_POST}" \
  -H "Authorization: Bearer $READER_ID_TOKEN" | jq '{entitled, body}'

curl -fsS -X POST "http://${ALB_DNS}/v1/gifts" \
  -H "Authorization: Bearer $READER_ID_TOKEN" \
  -H "Idempotency-Key: $(newkey)" \
  -H "Content-Type: application/json" \
  -d "{\"publication_id\":\"$PUB_ID\",\"amount_cents\":1000,\"message\":\"AWS smoke gift\"}" \
  | jq '{status,bill}'

curl -fsS "http://${ALB_DNS}/v1/publications/${PUB_ID}/summary" \
  -H "Authorization: Bearer $READER_ID_TOKEN" \
  | jq '{subscriber_count,post_count,recent_revenue_cents}'
```

Expected result: subscribe returns 201 with a bill, the reader post read returns
`entitled:true` and the body, gift returns `status:"pending"` with
`total_charged_cents:1080`, and summary counters include the subscription, post,
and API-side revenue source rows. Same idempotency-key replays must not create a
second subscription or gift.

## 18. AWS Worker Delivery Verification

The paid subscription and gift create Sprint-4 routable outbox events. Allow the
worker a short polling interval, then inspect the delivery path and receipts:

```bash
aws logs tail "/ecs/${PROJECT}-${ENVIRONMENT}-worker" --since 10m

aws sqs get-queue-attributes \
  --queue-url "$WORKER_QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

aws s3api list-objects-v2 \
  --bucket "$RECEIPT_BUCKET" \
  --prefix receipts/ \
  --query 'Contents[].Key' \
  --output text

aws sqs get-queue-attributes \
  --queue-url "$WORKER_DLQ_URL" \
  --attribute-names ApproximateNumberOfMessages
aws sqs get-queue-attributes \
  --queue-url "$EVENT_DELIVERY_DLQ_URL" \
  --attribute-names ApproximateNumberOfMessages
```

Expected: worker logs show claimed/published/processed commerce events; the
primary queue drains; receipt keys exist for the paid subscription and gift; and
both DLQ depths remain zero. Do not purge or replay a DLQ during this smoke test.
`post.published` remains pending until Sprint 5 supplies newsletter routing and
handlers; its absence from worker receipts is expected.

## 19. AWS Web Setup Boundary

Current local web behavior:

- `NEXT_PUBLIC_AUTH_MODE=local` uses local passwordless `/local/auth/*`.
- Local web can create plans, subscribe to paid plans, unlock paid posts, and
  send gifts against the API.
- The production web build uses system/local fonts and should not require a live
  Google Fonts fetch.
- `NEXT_PUBLIC_AUTH_MODE=production` does not yet implement the Cognito PKCE
  browser callback.

Before full hosted AWS browser acceptance, add a web production auth adapter
that:

1. Builds the Cognito hosted UI authorization URL with PKCE.
2. Handles `/auth/callback`.
3. Exchanges the code at Cognito `/oauth2/token`.
4. Stores the ID token in session storage.
5. Calls `/v1/me`.
6. Clears tokens on sign-out and redirects to the Cognito logout endpoint.

Then configure Cognito callback/logout URLs to the hosted web origin in
Terraform before applying:

```hcl
callback_urls = ["https://<web-host>/auth/callback"]
logout_urls   = ["https://<web-host>/"]
```

The current Cognito module supports these variables, but the environment layer
must expose and pass them if you do not use the module defaults.

## 20. Cost Control and Teardown

Scale API tasks to zero when idle:

```hcl
api_desired_count = 0
worker_desired_count = 0
```

Then:

```bash
terraform -chdir="$TF_ENV_DIR" plan -out=tfplan
terraform -chdir="$TF_ENV_DIR" apply tfplan
```

Destroying the environment is destructive and requires explicit approval:

```bash
terraform -chdir="$TF_ENV_DIR" destroy
```

Current RDS module settings are demo-friendly: `deletion_protection=false` and
`skip_final_snapshot=true`. For a real production environment, change those
defaults before the first production apply.

## 21. Acceptance Checklist

- IAM Identity Center profile works with `aws sts get-caller-identity`.
- Terraform `prod` exists separately from `dev`.
- Terraform fmt/init/validate/plan pass.
- ECR image push succeeds.
- API and worker image pushes succeed.
- RDS is private and encrypted.
- ElastiCache is private.
- App database URL exists only in Secrets Manager.
- API and worker ECS services stabilize.
- Alembic one-off ECS task exits 0.
- Demo seed one-off ECS task exits 0 and is idempotent.
- ALB `/healthz` returns 200.
- Cognito ID token works against `/v1/me`.
- `owner=me` does not leak other users' publications.
- Create/edit/publish/read/archive API smoke passes.
- Plan/subscribe/gift/paid-entitlement API smoke passes.
- Worker delivery smoke shows receipts and empty worker/EventBridge DLQs.
- Hosted web smoke is marked complete only after production PKCE is implemented.

## 22. Official References

- AWS CLI IAM Identity Center configuration:
  <https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html>
- AWS IAM best practices:
  <https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html>
- Amazon ECR private registry authentication:
  <https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html>
- Amazon ECS task execution role:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html>
- AWS Secrets Manager secret creation:
  <https://docs.aws.amazon.com/secretsmanager/latest/userguide/create_secret.html>
- RDS password management with Secrets Manager:
  <https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html>
- Cognito authorization endpoint:
  <https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html>
- Cognito token endpoint:
  <https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html>
- EventBridge targets and delivery retries:
  <https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-targets.html>
- Amazon SQS dead-letter queues:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html>
- Amazon S3 bucket versioning:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html>
- Terraform S3 backend:
  <https://developer.hashicorp.com/terraform/language/backend/s3>
