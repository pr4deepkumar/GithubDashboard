output "dashboard_file" {
  description = "Rendered dashboard HTML file path."
  value       = local_file.dashboard_html.filename
}

output "dashboard_generated_at" {
  description = "UTC timestamp when data was fetched."
  value       = data.external.github_dashboard.result.generated_at
}

output "s3_website_url" {
  description = "Public S3 website URL when aws_bucket_name is configured."
  value       = var.aws_bucket_name != "" ? "http://${aws_s3_bucket.dashboard[0].bucket}.s3-website-${var.aws_region}.amazonaws.com" : null
}

output "lambda_refresh_function_name" {
  description = "Lambda function name when auto refresh is enabled."
  value       = local.lambda_enabled ? aws_lambda_function.dashboard_refresh[0].function_name : null
}

output "lambda_refresh_schedule_expression" {
  description = "EventBridge schedule for dashboard refresh Lambda."
  value       = local.lambda_enabled ? aws_cloudwatch_event_rule.dashboard_refresh[0].schedule_expression : null
}
