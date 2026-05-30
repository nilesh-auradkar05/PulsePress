provider "aws" {
  region = var.aws_region

  # Every resource is tagged for cost attribution and teardown (SPEC §14, ADR-0007).
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
