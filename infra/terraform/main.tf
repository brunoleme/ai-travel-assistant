terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Pass bucket + region via -backend-config or backend.hcl (from .env).
    # Example: terraform init -backend-config="bucket=YOUR_TF_STATE_BUCKET" -backend-config="region=us-east-1"
    key     = "ingestion/terraform.tfstate"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
}

module "ingestion" {
  source = "./ingestion"

  project     = var.project
  environment = var.environment
  owner       = var.owner
}
