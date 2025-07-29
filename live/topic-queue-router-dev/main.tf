# Topic Queue Router - Development Environment
# High-performance Lambda router for Kafka to SQS routing

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  backend "s3" {
    bucket         = "tfstate-1800battery-dev-20250521122328"
    key            = "topic-queue-router/topic-queue-router-dev/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment   = "dev"
      Project       = "topic-queue-router"
      ManagedBy     = "terraform"
      Component     = "queue-routing"
      CostOptimized = "true"
    }
  }
}

# Data sources for existing infrastructure
data "aws_vpc" "main" {
  default = true
}

# Remote state for MSK cluster
data "terraform_remote_state" "msk" {
  backend = "s3"
  config = {
    bucket = "tfstate-1800battery-dev-20250521122328"
    key    = "kafka-infrastructure/msk-cluster-dev/terraform.tfstate"
    region = "us-west-2"
  }
}

# Local configuration
locals {
  environment = "dev"
}

# Topic Queue Router module
module "topic_queue_router" {
  source = "../../modules/topic-queue-router"

  environment             = local.environment
  kafka_cluster_name      = "marketring-msk-cluster-${local.environment}"
  vpc_id                  = data.aws_vpc.main.id
  msk_security_group_id   = data.terraform_remote_state.msk.outputs.client_access_security_group_id
  log_level              = var.log_level
  log_retention_days     = 7
  aws_region             = var.aws_region
}