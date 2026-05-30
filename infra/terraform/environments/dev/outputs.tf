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
