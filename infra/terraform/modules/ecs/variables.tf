variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (for the awslogs driver)."
  type        = string
}

variable "environment_name" {
  description = "Value for the PULSEPRESS_ENVIRONMENT task env var."
  type        = string
  default     = "dev"
}

variable "public_subnet_ids" {
  description = "Subnets the Fargate tasks run in (public, with public IP)."
  type        = list(string)
}

variable "service_security_group_id" {
  description = "Security group for the API tasks (created at the environment level)."
  type        = string
}

variable "api_image" {
  description = "Fully-qualified API container image (repo URL : tag)."
  type        = string
}

variable "api_container_port" {
  type    = number
  default = 8000
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "worker_image" {
  description = "Fully-qualified worker container image (repo URL : tag)."
  type        = string
}

variable "worker_desired_count" {
  description = "Number of worker tasks to run (0 scales worker processing to zero)."
  type        = number
  default     = 1
}

variable "worker_environment" {
  description = "Non-secret worker environment variables."
  type        = map(string)
  default     = {}
}

variable "worker_secret_environment" {
  description = "Worker env vars sourced from Secrets Manager (name => secret ARN / valueFrom)."
  type        = map(string)
  default     = {}
}

variable "worker_task_policy" {
  description = "JSON IAM policy granting the worker access to its queue, event bus, and receipt bucket."
  type        = string
}

variable "target_group_arn" {
  description = "ALB target group the service registers into."
  type        = string
}

variable "extra_environment" {
  description = "Additional non-secret task environment variables."
  type        = map(string)
  default     = {}
}

variable "secret_environment" {
  description = "Task env vars sourced from Secrets Manager (name => secret ARN / valueFrom)."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  type    = number
  default = 14
}
