variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (for the awslogs driver)."
  type        = string
}

variable "vpc_id" {
  description = "VPC id the service security group lives in."
  type        = string
}

variable "public_subnet_ids" {
  description = "Subnets the Fargate tasks run in (public, with public IP)."
  type        = list(string)
}

variable "api_image" {
  description = "Fully-qualified API container image (repo URL : tag)."
  type        = string
}

variable "api_container_port" {
  description = "Port the API container listens on."
  type        = number
  default     = 8000
}

variable "api_desired_count" {
  description = "Number of API tasks to run."
  type        = number
  default     = 1
}

variable "alb_security_group" {
  description = "ALB security group id allowed to reach the tasks."
  type        = string
}

variable "target_group_arn" {
  description = "ALB target group the service registers into."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the API service."
  type        = number
  default     = 14
}
