# ---- S3 ----
resource "aws_s3_bucket" "raw_ingestion" {
  bucket = "${local.name_prefix}-raw"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-raw"
  })
}

resource "aws_s3_bucket" "processed_artifacts" {
  bucket = "${local.name_prefix}-processed"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-processed"
  })
}

# ---- SQS: DLQ first (main queue references it) ----
resource "aws_sqs_queue" "ingestion_dlq" {
  name = "${local.name_prefix}-dlq"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-dlq"
  })
}

resource "aws_sqs_queue" "ingestion" {
  name = "${local.name_prefix}-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-queue"
  })
}

# ---- IAM: policy for ingestion workers ----
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_policy" "ingestion_worker" {
  name        = "${local.name_prefix}-worker-policy"
  description = "S3 and SQS access for ingestion pipeline workers"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Raw"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw_ingestion.arn,
          "${aws_s3_bucket.raw_ingestion.arn}/*"
        ]
      },
      {
        Sid    = "S3Processed"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.processed_artifacts.arn,
          "${aws_s3_bucket.processed_artifacts.arn}/*"
        ]
      },
      {
        Sid    = "SQSIngestion"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.ingestion.arn,
          aws_sqs_queue.ingestion_dlq.arn
        ]
      }
    ]
  })
}
