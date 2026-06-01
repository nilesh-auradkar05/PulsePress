variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "Private subnets for the cache subnet group."
  type        = list(string)
}

variable "source_security_group_id" {
  description = "Security group allowed to reach Redis (the API service SG)."
  type        = string
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}
