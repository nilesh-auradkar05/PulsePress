output "alb_dns_name" {
  description = "Public DNS name of the API load balancer (hit /healthz here)."
  value       = module.alb.dns_name
}

output "ecr_repository_urls" {
  description = "Map of ECR repository name to URL."
  value       = module.ecr.repository_urls
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  value       = module.ecs.cluster_name
}

output "rds_endpoint" {
  description = "RDS Postgres host address."
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis host address."
  value       = module.elasticache.endpoint
}

output "cognito_issuer" {
  description = "Cognito OIDC issuer URL."
  value       = module.cognito.issuer
}

output "cognito_client_id" {
  description = "Cognito app client id (JWT audience)."
  value       = module.cognito.client_id
}
