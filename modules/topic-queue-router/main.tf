# Topic Queue Router - Terraform Configuration
# High-performance Lambda router for Kafka to SQS routing

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
}

# Local variables
locals {
  environment = var.environment
  
  # Lambda configuration
  lambda_timeout = 60
  lambda_memory  = 512
  
  # SQS queue names
  queue_names = {
    small  = "${local.environment}-small-products-queue"
    medium = "${local.environment}-medium-products-queue"
    large  = "${local.environment}-large-products-queue"
  }
  
  dlq_names = {
    small  = "${local.environment}-small-products-dlq"
    medium = "${local.environment}-medium-products-dlq"
    large  = "${local.environment}-large-products-dlq"
  }
  
  common_tags = {
    Environment = local.environment
    Project     = "marketring-topic-queue-router"
    ManagedBy   = "terraform"
    Component   = "queue-routing"
  }
}

# Data sources for existing infrastructure
data "aws_msk_cluster" "kafka" {
  cluster_name = var.kafka_cluster_name
}

data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  filter {
    name   = "tag:Type"
    values = ["private"]
  }
}

# Dead Letter Queues
resource "aws_sqs_queue" "dlq" {
  for_each = local.dlq_names
  
  name                      = each.value
  message_retention_seconds = 1209600  # 14 days
  
  tags = merge(local.common_tags, {
    Name      = each.value
    QueueType = "dlq"
    Purpose   = "${each.key}-products-dlq"
  })
}

# Main SQS Queues
resource "aws_sqs_queue" "products" {
  for_each = local.queue_names
  
  name                       = each.value
  visibility_timeout_seconds = each.key == "small" ? 300 : (each.key == "medium" ? 600 : 900)
  message_retention_seconds  = 1209600  # 14 days
  
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 3
  })
  
  tags = merge(local.common_tags, {
    Name      = each.value
    QueueType = each.key
    Purpose   = "${each.key}-products-queue"
  })
}

# Lambda execution role
resource "aws_iam_role" "lambda_role" {
  name = "${local.environment}-topic-queue-router-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# Lambda execution policy
resource "aws_iam_policy" "lambda_policy" {
  name = "${local.environment}-topic-queue-router-policy"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AttachNetworkInterface",
          "ec2:DetachNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka:DescribeCluster",
          "kafka:GetBootstrapBrokers",
          "kafka:DescribeClusterV2"
        ]
        Resource = data.aws_msk_cluster.kafka.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:SendMessageBatch"
        ]
        Resource = [
          for queue in aws_sqs_queue.products : queue.arn
        ]
      }
    ]
  })
  
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Security group for Lambda
resource "aws_security_group" "lambda_sg" {
  name_prefix = "${local.environment}-topic-router-lambda-"
  vpc_id      = var.vpc_id
  description = "Security group for topic queue router Lambda"
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.environment}-topic-router-lambda-sg"
  })
}

# Package Lambda function
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../src"
  output_path = "${path.module}/router.zip"
  excludes    = ["tests", "__pycache__", "*.pyc"]
}

# Lambda function
resource "aws_lambda_function" "router" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${local.environment}-topic-queue-router"
  role            = aws_iam_role.lambda_role.arn
  handler         = "router.lambda_handler"
  runtime         = "python3.11"
  timeout         = local.lambda_timeout
  memory_size     = local.lambda_memory
  architectures   = ["arm64"]  # Better price/performance
  
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  
  vpc_config {
    subnet_ids         = data.aws_subnets.private.ids
    security_group_ids = [aws_security_group.lambda_sg.id, var.msk_security_group_id]
  }
  
  environment {
    variables = {
      ENVIRONMENT       = local.environment
      SMALL_QUEUE_URL   = aws_sqs_queue.products["small"].url
      MEDIUM_QUEUE_URL  = aws_sqs_queue.products["medium"].url
      LARGE_QUEUE_URL   = aws_sqs_queue.products["large"].url
      POWERTOOLS_SERVICE_NAME = "topic-queue-router"
      POWERTOOLS_LOG_LEVEL    = var.log_level
    }
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.environment}-topic-queue-router"
  })
  
  depends_on = [
    aws_iam_role_policy_attachment.lambda_policy,
    aws_iam_role_policy_attachment.lambda_vpc_execution,
    aws_cloudwatch_log_group.lambda_logs
  ]
}

# CloudWatch log group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.environment}-topic-queue-router"
  retention_in_days = var.log_retention_days
  
  tags = local.common_tags
}

# MSK event source mapping
resource "aws_lambda_event_source_mapping" "kafka_trigger" {
  event_source_arn  = data.aws_msk_cluster.kafka.arn
  function_name     = aws_lambda_function.router.arn
  topics            = ["product-applications-updates-${local.environment}"]
  starting_position = "LATEST"
  batch_size        = 100
  maximum_batching_window_in_seconds = 5
  
  depends_on = [aws_lambda_function.router]
}

# CloudWatch alarms
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.environment}-topic-router-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors Lambda function errors"
  
  dimensions = {
    FunctionName = aws_lambda_function.router.function_name
  }
  
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${local.environment}-topic-router-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "45000"  # 45 seconds (75% of timeout)
  alarm_description   = "This metric monitors Lambda function duration"
  
  dimensions = {
    FunctionName = aws_lambda_function.router.function_name
  }
  
  tags = local.common_tags
}