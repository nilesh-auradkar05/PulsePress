output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "API ECS service name."
  value       = aws_ecs_service.api.name
}

output "log_group_name" {
  description = "CloudWatch log group for the API service."
  value       = aws_cloudwatch_log_group.api.name
}
