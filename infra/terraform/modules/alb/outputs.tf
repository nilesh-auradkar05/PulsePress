output "dns_name" {
  description = "Public DNS name of the ALB."
  value       = aws_lb.this.dns_name
}

output "target_group_arn" {
  description = "ARN of the API target group."
  value       = aws_lb_target_group.this.arn
}

output "security_group_id" {
  description = "ALB security group id (source for the service SG ingress)."
  value       = aws_security_group.alb.id
}

output "listener_arn" {
  description = "ARN of the HTTP listener."
  value       = aws_lb_listener.http.arn
}
