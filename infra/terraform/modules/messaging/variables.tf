variable "name_prefix" {
  description = "Prefix for worker delivery resources."
  type        = string
}

variable "max_receive_count" {
  description = "SQS receives allowed before an undelivered message moves to the DLQ."
  type        = number
  default     = 5

  validation {
    condition     = var.max_receive_count >= 1 && var.max_receive_count <= 100
    error_message = "max_receive_count must be between 1 and 100."
  }
}

variable "visibility_timeout_seconds" {
  description = "Primary queue visibility timeout; must exceed the worker lease duration."
  type        = number
  default     = 360

  validation {
    condition     = var.visibility_timeout_seconds >= 30
    error_message = "visibility_timeout_seconds must be at least 30 seconds."
  }
}

variable "dead_letter_retention_seconds" {
  description = "Retention period for operator inspection of DLQ messages."
  type        = number
  default     = 1209600
}
