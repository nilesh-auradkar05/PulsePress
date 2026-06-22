variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project tag applied to every resource."
  type        = string
  default     = "pulsepress"
}

variable "environment" {
  description = "Environment name (dev/prod)."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "api_image_tag" {
  description = "Image tag for the API task definition (set by the deploy pipeline)."
  type        = string
  default     = "bootstrap"
}

variable "worker_image_tag" {
  description = "Image tag for the worker task definition (set by the deploy pipeline)."
  type        = string
  default     = "bootstrap"
}

variable "api_desired_count" {
  description = "Number of API tasks to run (0 scales the service to zero)."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Number of worker tasks to run (0 scales worker processing to zero)."
  type        = number
  default     = 1
}

variable "cognito_domain_prefix" {
  description = "Cognito hosted-UI domain prefix (must be globally unique)."
  type        = string
  default     = "pulsepress-dev-auth"
}
