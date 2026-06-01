output "user_pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "client_id" {
  description = "App client id — the API's expected JWT audience."
  value       = aws_cognito_user_pool_client.this.id
}

output "issuer" {
  description = "OIDC issuer URL (PULSEPRESS_COGNITO_ISSUER)."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}

output "jwks_url" {
  value = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.this.id}/.well-known/jwks.json"
}

output "hosted_ui_domain" {
  value = "${aws_cognito_user_pool_domain.this.domain}.auth.${var.aws_region}.amazoncognito.com"
}
