output "raw_bucket_name" {
  description = "Name of the raw ingestion S3 bucket"
  value       = aws_s3_bucket.raw_ingestion.id
}

output "processed_bucket_name" {
  description = "Name of the processed artifacts S3 bucket"
  value       = aws_s3_bucket.processed_artifacts.id
}

output "ingestion_queue_url" {
  description = "URL of the main ingestion SQS queue"
  value       = aws_sqs_queue.ingestion.url
}

output "ingestion_dlq_url" {
  description = "URL of the ingestion dead-letter SQS queue"
  value       = aws_sqs_queue.ingestion_dlq.url
}

output "ingestion_worker_policy_arn" {
  description = "ARN of the IAM policy for ingestion workers"
  value       = aws_iam_policy.ingestion_worker.arn
}
