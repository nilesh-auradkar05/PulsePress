data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix = "${var.project}-${var.environment}"
  azs         = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "network" {
  source = "../../modules/network"

  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  azs         = local.azs
}

module "ecr" {
  source = "../../modules/ecr"

  repositories = ["${var.project}-api", "${var.project}-worker"]
}

module "alb" {
  source = "../../modules/alb"

  name_prefix       = local.name_prefix
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  target_port       = 8000
  health_check_path = "/healthz"
}

# API service security group, defined here (not in the ecs module) so RDS and
# Redis can allow ingress from it without creating a module dependency cycle.
resource "aws_security_group" "service" {
  name        = "${local.name_prefix}-api-sg"
  description = "API Fargate tasks."
  vpc_id      = module.network.vpc_id

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-api-sg" }
}

resource "aws_security_group_rule" "service_from_alb" {
  type                     = "ingress"
  description              = "API container port from the ALB"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.service.id
  source_security_group_id = module.alb.security_group_id
}

# Container for the API's full DATABASE_URL. Created empty here — the value is
# composed from the RDS endpoint + AWS-managed master password and set
# out-of-band (never committed, never in Terraform state).
resource "aws_secretsmanager_secret" "app_database_url" {
  name        = "${local.name_prefix}/database-url"
  description = "SQLAlchemy DATABASE_URL for the API service (populated out-of-band)."
}

module "rds" {
  source = "../../modules/rds"

  name_prefix              = local.name_prefix
  vpc_id                   = module.network.vpc_id
  private_subnet_ids       = module.network.private_subnet_ids
  source_security_group_id = aws_security_group.service.id
}

module "elasticache" {
  source = "../../modules/elasticache"

  name_prefix              = local.name_prefix
  vpc_id                   = module.network.vpc_id
  private_subnet_ids       = module.network.private_subnet_ids
  source_security_group_id = aws_security_group.service.id
}

module "cognito" {
  source = "../../modules/cognito"

  name_prefix   = local.name_prefix
  aws_region    = var.aws_region
  domain_prefix = var.cognito_domain_prefix
}

module "ecs" {
  source = "../../modules/ecs"

  name_prefix               = local.name_prefix
  aws_region                = var.aws_region
  environment_name          = var.environment
  public_subnet_ids         = module.network.public_subnet_ids
  service_security_group_id = aws_security_group.service.id
  api_image                 = "${module.ecr.repository_urls["${var.project}-api"]}:${var.api_image_tag}"
  api_container_port        = 8000
  api_desired_count         = var.api_desired_count
  target_group_arn          = module.alb.target_group_arn

  extra_environment = {
    PULSEPRESS_COGNITO_ISSUER   = module.cognito.issuer
    PULSEPRESS_COGNITO_AUDIENCE = module.cognito.client_id
    PULSEPRESS_REDIS_URL        = "redis://${module.elasticache.endpoint}:${module.elasticache.port}/0"
  }
  secret_environment = {
    PULSEPRESS_DATABASE_URL = aws_secretsmanager_secret.app_database_url.arn
  }

  # The ALB listener must exist before the service registers with the target group.
  depends_on = [module.alb]
}
