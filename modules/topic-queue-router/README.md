# Topic Queue Router Module

This Terraform module creates a high-performance Lambda function that consumes messages from an MSK (Managed Streaming for Apache Kafka) cluster and routes them to different SQS queues based on message attributes.

## Features

- **AWS Best Practices**: Follows AWS recommendations for Lambda-MSK integration
- **Complete IAM Permissions**: Includes all required permissions for MSK event source mapping
- **VPC Support**: Properly configured for Lambda functions running in VPC with MSK
- **High Performance**: Processes up to 100 messages per batch with concurrent SQS sends
- **Dead Letter Queue**: Each queue has its own DLQ for failed messages
- **CloudWatch Monitoring**: Includes alarms for errors and duration

## IAM Permissions

The module implements comprehensive IAM permissions following AWS best practices:

### Default Mode (Recommended)
By default, the module creates a custom IAM policy with all necessary permissions:
- CloudWatch Logs permissions
- VPC networking permissions (including `ec2:DescribeSecurityGroups`, `ec2:DescribeSubnets`, `ec2:DescribeVpcs`)
- MSK cluster permissions (`kafka:DescribeClusterV2`, `kafka:GetBootstrapBrokers`)
- SQS destination permissions

### AWS Managed Policy Mode
Optionally, you can use the AWS managed `AWSLambdaMSKExecutionRole` policy by setting `use_aws_managed_msk_policy = true`. This approach:
- Uses AWS managed policy for VPC and MSK permissions
- Still requires custom policy for SQS permissions
- May be preferred in organizations that mandate using AWS managed policies

## Usage

```hcl
module "topic_queue_router" {
  source = "../../modules/topic-queue-router"

  environment             = "dev"
  kafka_cluster_name      = "marketring-msk-dev"
  vpc_id                  = data.aws_vpc.main.id
  msk_security_group_id   = data.terraform_remote_state.msk.outputs.client_access_security_group_id
  
  # Optional: Use AWS managed policy instead of custom policy
  # use_aws_managed_msk_policy = true
  
  log_level          = "INFO"
  log_retention_days = 7
  aws_region         = "us-west-2"
}
```

## Requirements

- MSK cluster must be running and accessible
- VPC with private subnets for Lambda execution
- Security group that allows Lambda to connect to MSK brokers
- Kafka topic must exist before enabling the event source mapping

## Troubleshooting

### Event Source Mapping Disabled
If the Lambda event source mapping gets disabled with "Lambda does not have enough permission" error:
1. Ensure all EC2 describe permissions are included (especially `ec2:DescribeSecurityGroups`)
2. Check that the Lambda execution role has been updated with the latest policy
3. Verify security group rules allow Lambda to reach MSK brokers on port 9098 (IAM auth)

### Network Connectivity Issues
- Ensure Lambda and MSK are in the same VPC
- Verify security group rules allow outbound traffic from Lambda to MSK
- Check that MSK security group allows inbound traffic from Lambda security group

## Outputs

- `lambda_function_arn`: ARN of the Lambda function
- `lambda_function_name`: Name of the Lambda function
- `sqs_queue_urls`: Map of queue type to SQS queue URLs
- `lambda_role_arn`: ARN of the Lambda execution role