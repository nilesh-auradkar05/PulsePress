# Local state for the walking skeleton. Migrate to an S3 backend (with a
# DynamoDB lock table) before the first real multi-operator deploy.
terraform {
  backend "local" {}
}
