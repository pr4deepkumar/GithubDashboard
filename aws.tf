provider "aws" {
  region = var.aws_region

  # Keep local-only runs working when AWS deploy is disabled.
  skip_credentials_validation = var.aws_bucket_name == ""
  skip_requesting_account_id  = var.aws_bucket_name == ""
  skip_metadata_api_check     = var.aws_bucket_name == ""
}

resource "aws_s3_bucket" "dashboard" {
  count         = var.aws_bucket_name != "" ? 1 : 0
  bucket        = var.aws_bucket_name
  force_destroy = var.aws_force_destroy
}

resource "aws_s3_bucket_ownership_controls" "dashboard" {
  count  = var.aws_bucket_name != "" ? 1 : 0
  bucket = aws_s3_bucket.dashboard[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "dashboard" {
  count  = var.aws_bucket_name != "" ? 1 : 0
  bucket = aws_s3_bucket.dashboard[0].id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "dashboard" {
  count  = var.aws_bucket_name != "" ? 1 : 0
  bucket = aws_s3_bucket.dashboard[0].id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket_policy" "dashboard_public_read" {
  count      = var.aws_bucket_name != "" ? 1 : 0
  bucket     = aws_s3_bucket.dashboard[0].id
  depends_on = [aws_s3_bucket_public_access_block.dashboard]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadDashboard"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["s3:GetObject"]
        Resource  = ["${aws_s3_bucket.dashboard[0].arn}/*"]
      }
    ]
  })
}

resource "aws_s3_object" "dashboard_index" {
  count        = var.aws_bucket_name != "" ? 1 : 0
  bucket       = aws_s3_bucket.dashboard[0].id
  key          = "index.html"
  content      = local.rendered_dashboard
  content_type = "text/html; charset=utf-8"
  etag         = md5(local.rendered_dashboard)

  depends_on = [
    aws_s3_bucket_website_configuration.dashboard,
    aws_s3_bucket_policy.dashboard_public_read,
    aws_s3_bucket_ownership_controls.dashboard,
  ]
}
