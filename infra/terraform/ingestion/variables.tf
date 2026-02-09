variable "project" {
  description = "Project name for tagging"
  type        = string
}

variable "environment" {
  description = "Environment (e.g. dev, staging, prod)"
  type        = string
}

variable "owner" {
  description = "Owner for tagging"
  type        = string
}

locals {
  common_tags = {
    project     = var.project
    environment = var.environment
    owner       = var.owner
  }
  name_prefix = "${var.project}-${var.environment}-ingestion"
}
