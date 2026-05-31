variable "name_prefix" {
  type = string
}

variable "aws_region" {
  description = "Region (used to construct the issuer URL)."
  type        = string
}

variable "domain_prefix" {
  description = "Hosted-UI domain prefix (must be globally unique)."
  type        = string
}

variable "callback_urls" {
  type    = list(string)
  default = ["http://localhost:3000/auth/callback"]
}

variable "logout_urls" {
  type    = list(string)
  default = ["http://localhost:3000"]
}
