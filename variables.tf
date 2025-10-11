variable "github_token" {
  description = "Optional GitHub personal access token for higher API limits and private repo access."
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_username" {
  description = "GitHub username to build dashboard for. You can also set github_profile instead."
  type        = string
  default     = ""
}

variable "github_profile" {
  description = "GitHub profile URL or username to analyze, for example https://github.com/octocat or octocat."
  type        = string
  default     = ""
}

variable "organizations" {
  description = "Optional org logins to include in repository list."
  type        = list(string)
  default     = []
}

variable "include_private_repos" {
  description = "Include private repositories in recent repositories list."
  type        = bool
  default     = true
}

variable "max_repositories" {
  description = "Maximum number of repositories displayed."
  type        = number
  default     = 20
}

variable "max_items_per_section" {
  description = "Maximum items shown in each issue/PR section."
  type        = number
  default     = 20
}

variable "output_file" {
  description = "Path where rendered dashboard HTML will be written."
  type        = string
  default     = "dashboard.html"
}

variable "aws_region" {
  description = "AWS region where S3 bucket resources are managed."
  type        = string
  default     = "us-east-1"
}

variable "aws_bucket_name" {
  description = "Optional S3 bucket name to publish dashboard as index.html. Leave empty to skip AWS publish."
  type        = string
  default     = ""
}

variable "aws_force_destroy" {
  description = "Allow Terraform/OpenTofu to delete non-empty S3 bucket on destroy."
  type        = bool
  default     = false
}

variable "enable_lambda_auto_refresh" {
  description = "Enable scheduled Lambda refresh that writes updated dashboard HTML to S3."
  type        = bool
  default     = false
}

variable "lambda_schedule_expression" {
  description = "EventBridge schedule for Lambda refresh, for example rate(6 hours)."
  type        = string
  default     = "rate(6 hours)"
}

variable "lambda_log_retention_days" {
  description = "CloudWatch Logs retention for dashboard Lambda."
  type        = number
  default     = 14
}
