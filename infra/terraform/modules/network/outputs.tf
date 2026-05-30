output "vpc_id" {
  description = "VPC id."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet ids (ALB + public-IP Fargate tasks)."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet ids (reserved for Sprint 2 RDS/Redis)."
  value       = aws_subnet.private[*].id
}
