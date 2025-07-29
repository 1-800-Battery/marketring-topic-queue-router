# Outputs for Topic Queue Router - Development Environment

output "lambda_function_arn" {
  description = "ARN of the topic queue router Lambda function"
  value       = module.topic_queue_router.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the topic queue router Lambda function"
  value       = module.topic_queue_router.lambda_function_name
}

output "sqs_queue_urls" {
  description = "URLs of the SQS queues"
  value       = module.topic_queue_router.sqs_queue_urls
}

output "sqs_queue_arns" {
  description = "ARNs of the SQS queues"
  value       = module.topic_queue_router.sqs_queue_arns
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for Lambda function"
  value       = module.topic_queue_router.cloudwatch_log_group
}