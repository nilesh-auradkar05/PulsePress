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

module "ecs" {
  source = "../../modules/ecs"

  name_prefix        = local.name_prefix
  aws_region         = var.aws_region
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  api_image          = "${module.ecr.repository_urls["${var.project}-api"]}:${var.api_image_tag}"
  api_container_port = 8000
  api_desired_count  = var.api_desired_count
  alb_security_group = module.alb.security_group_id
  target_group_arn   = module.alb.target_group_arn

  # The ALB listener must exist before the service can register with the target group.
  depends_on = [module.alb]
}
