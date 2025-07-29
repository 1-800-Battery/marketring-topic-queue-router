# Variables for Topic Queue Router - Development Environment

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "log_level" {
  description = "Lambda function log level"
  type        = string
  default     = "INFO"
}