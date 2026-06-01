output "endpoint" {
  description = "RDS host address."
  value       = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "username" {
  value = aws_db_instance.this.username
}

output "master_user_secret_arn" {
  description = "ARN of the AWS-managed master credential secret (compose the app DATABASE_URL from this)."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
