# Terraform — AI Travel Assistant

## Remote state (S3)

State is stored in S3. Use `.env` for bucket and region:

- `TF_STATE_BUCKET` — S3 bucket for Terraform state (e.g. `ai-travel-assistant-tfstate`)
- `AWS_REGION` — Region for state and resources

**First-time or re-init:**

```bash
# From repo root
make tf-init-backend
```

This runs `terraform init -reconfigure` with `-backend-config` from `configs/.env`.

## IAM permissions for Terraform (apply)

The IAM user/role used for `terraform apply` (via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) must be allowed to:

- **S3:** Create buckets, get/put bucket tagging, list (e.g. `s3:CreateBucket`, `s3:GetBucketTagging`, `s3:PutBucketTagging`, `s3:ListBucket`, plus object actions if you add more resources).
- **SQS:** Create queues, get/set attributes, tag (e.g. `sqs:CreateQueue`, `sqs:GetQueueAttributes`, `sqs:SetQueueAttributes`, `sqs:TagQueue`).
- **IAM:** Create and manage policies (e.g. `iam:CreatePolicy`, `iam:GetPolicy`, `iam:TagPolicy`).

If `terraform apply` fails with `AccessDenied` on e.g. `s3:GetBucketTagging`, attach a policy that allows the S3/SQS/IAM actions above (or use a managed policy like `AmazonS3FullAccess`, `AmazonSQSFullAccess`, `IAMFullAccess` for development).

## Plan and apply

```bash
make tf-plan    # writes tfplan
make tf-apply   # applies (or: cd infra/terraform && terraform apply tfplan)
```

After a successful apply, get outputs (queue URLs, bucket names) for the ingestion service:

```bash
cd infra/terraform && terraform output
```

Use these values in `configs/.env` when running the ingestion worker in AWS mode:

- `INGESTION_QUEUE_URL` — main queue URL (from `terraform output ingestion_queue_url`)
- `INGESTION_DLQ_URL` — DLQ URL (from `terraform output ingestion_dlq_url`)
- Optionally `RAW_BUCKET`, `PROCESSED_BUCKET` for future S3 artifact use
- `YTDLP_COOKIES_FILE` — (optional) path to a cookies file for yt-dlp when YouTube blocks anonymous requests; see [yt-dlp FAQ on cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)

Then run the worker with AWS credentials and:

```bash
INGESTION_MODE=aws make run-ingestion
```

(or set `INGESTION_MODE=aws` in `.env`). The worker must use credentials that have the ingestion worker IAM policy attached (see Terraform output `ingestion_worker_policy_arn`).
