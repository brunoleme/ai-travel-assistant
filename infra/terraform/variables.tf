variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name for tagging"
  type        = string
  default     = "ai-travel-assistant"
}

variable "environment" {
  description = "Environment (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner for tagging"
  type        = string
  default     = "platform"
}
