variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC id the ALB and target group live in."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnets for the internet-facing ALB."
  type        = list(string)
}

variable "target_port" {
  description = "Port the API container listens on."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "Health-check path on the target."
  type        = string
  default     = "/healthz"
}
