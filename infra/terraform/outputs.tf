output "raw_bucket_name" {
  description = "S3 bucket for raw ingestion artifacts"
  value       = module.ingestion.raw_bucket_name
}

output "processed_bucket_name" {
  description = "S3 bucket for processed artifacts"
  value       = module.ingestion.processed_bucket_name
}

output "ingestion_queue_url" {
  description = "SQS URL for the main ingestion queue"
  value       = module.ingestion.ingestion_queue_url
}

output "ingestion_dlq_url" {
  description = "SQS URL for the ingestion dead-letter queue"
  value       = module.ingestion.ingestion_dlq_url
}
