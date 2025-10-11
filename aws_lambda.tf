locals {
  lambda_enabled = var.enable_lambda_auto_refresh && var.aws_bucket_name != ""
}

data "archive_file" "dashboard_lambda_zip" {
  count       = local.lambda_enabled ? 1 : 0
  type        = "zip"
  source_file = "${path.module}/lambda/dashboard_refresher.py"
  output_path = "${path.module}/dashboard_refresher.zip"
}

resource "aws_iam_role" "dashboard_lambda" {
  count = local.lambda_enabled ? 1 : 0
  name  = "${replace(var.aws_bucket_name, ".", "-")}-dashboard-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "dashboard_lambda_inline" {
  count = local.lambda_enabled ? 1 : 0
  name  = "dashboard-lambda-inline-policy"
  role  = aws_iam_role.dashboard_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.dashboard[0].arn,
          "${aws_s3_bucket.dashboard[0].arn}/*",
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "dashboard_lambda" {
  count             = local.lambda_enabled ? 1 : 0
  name              = "/aws/lambda/${replace(var.aws_bucket_name, ".", "-")}-dashboard-refresh"
  retention_in_days = var.lambda_log_retention_days
}

resource "aws_lambda_function" "dashboard_refresh" {
  count = local.lambda_enabled ? 1 : 0

  function_name    = "${replace(var.aws_bucket_name, ".", "-")}-dashboard-refresh"
  role             = aws_iam_role.dashboard_lambda[0].arn
  runtime          = "python3.12"
  handler          = "dashboard_refresher.handler"
  filename         = data.archive_file.dashboard_lambda_zip[0].output_path
  source_code_hash = data.archive_file.dashboard_lambda_zip[0].output_base64sha256
  timeout          = 90
  memory_size      = 256

  environment {
    variables = {
      GITHUB_TOKEN           = var.github_token
      TARGET_GITHUB_PROFILE  = var.github_profile
      TARGET_GITHUB_USERNAME = var.github_username
      ORGANIZATIONS_CSV      = join(",", var.organizations)
      INCLUDE_PRIVATE        = tostring(var.include_private_repos)
      MAX_REPOSITORIES       = tostring(var.max_repositories)
      MAX_ITEMS_PER_SECTION  = tostring(var.max_items_per_section)
      OUTPUT_BUCKET          = var.aws_bucket_name
      OUTPUT_KEY             = "index.html"
    }
  }

  depends_on = [
    aws_iam_role_policy.dashboard_lambda_inline,
    aws_cloudwatch_log_group.dashboard_lambda,
  ]
}

resource "aws_cloudwatch_event_rule" "dashboard_refresh" {
  count               = local.lambda_enabled ? 1 : 0
  name                = "${replace(var.aws_bucket_name, ".", "-")}-dashboard-refresh-schedule"
  schedule_expression = var.lambda_schedule_expression
}

resource "aws_cloudwatch_event_target" "dashboard_refresh" {
  count     = local.lambda_enabled ? 1 : 0
  rule      = aws_cloudwatch_event_rule.dashboard_refresh[0].name
  target_id = "dashboard-refresh-lambda"
  arn       = aws_lambda_function.dashboard_refresh[0].arn
}

resource "aws_lambda_permission" "allow_events_invoke_dashboard_refresh" {
  count         = local.lambda_enabled ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dashboard_refresh[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.dashboard_refresh[0].arn
}
