# Variables for Topic Queue Router Terraform configuration

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "kafka_cluster_name" {
  description = "Name of the MSK cluster"
  type        = string
  default     = "marketring-msk-cluster"
}

variable "vpc_id" {
  description = "VPC ID where MSK cluster is deployed"
  type        = string
}

variable "msk_security_group_id" {
  description = "Security group ID for MSK client access"
  type        = string
}

variable "log_level" {
  description = "Lambda function log level"
  type        = string
  default     = "INFO"
  
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "Log level must be one of: DEBUG, INFO, WARNING, ERROR."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
  
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}