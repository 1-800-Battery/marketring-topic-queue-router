# Outputs for Topic Queue Router

output "lambda_function_arn" {
  description = "ARN of the topic queue router Lambda function"
  value       = aws_lambda_function.router.arn
}

output "lambda_function_name" {
  description = "Name of the topic queue router Lambda function"
  value       = aws_lambda_function.router.function_name
}

output "sqs_queue_urls" {
  description = "URLs of the SQS queues"
  value = {
    small  = aws_sqs_queue.products["small"].url
    medium = aws_sqs_queue.products["medium"].url
    large  = aws_sqs_queue.products["large"].url
  }
}

output "sqs_queue_arns" {
  description = "ARNs of the SQS queues"
  value = {
    small  = aws_sqs_queue.products["small"].arn
    medium = aws_sqs_queue.products["medium"].arn
    large  = aws_sqs_queue.products["large"].arn
  }
}

output "dlq_queue_urls" {
  description = "URLs of the dead letter queues"
  value = {
    small  = aws_sqs_queue.dlq["small"].url
    medium = aws_sqs_queue.dlq["medium"].url
    large  = aws_sqs_queue.dlq["large"].url
  }
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for Lambda function"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}