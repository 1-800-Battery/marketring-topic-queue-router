# Marketring Topic Queue Router

High-performance AWS Lambda function for routing Kafka messages from MSK to SQS queues based on queue type metadata.

## Architecture

This Lambda function consumes messages from the `product-applications-updates-{env}` Kafka topic and routes them to appropriate SQS queues based on the queue type metadata (`SMALL`, `MEDIUM`, `LARGE`) added by the ProductApplicationsCountTransform.

## Performance Features

- **Batch Processing**: Processes multiple Kafka messages in a single Lambda invocation
- **Connection Pooling**: Reuses SQS connections across invocations
- **Minimal Dependencies**: Optimized for cold start performance
- **Concurrent Processing**: Parallel SQS sends within batch
- **Error Handling**: Dead letter queue support with exponential backoff

## Queue Routing

| Queue Type | Target SQS Queue | Application Count Range |
|------------|------------------|-------------------------|
| `SMALL`    | `{env}-small-products-queue` | 1-50 applications |
| `MEDIUM`   | `{env}-medium-products-queue` | 51-200 applications |
| `LARGE`    | `{env}-large-products-queue` | 200+ applications |

## Message Flow

1. ProductApplicationsCountTransform publishes to Kafka topic with metadata:
   ```json
   {
     "productId": 12345,
     "applicationCount": 75,
     "queueType": "MEDIUM",
     "timestamp": "2025-01-15T10:30:00Z"
   }
   ```

2. Lambda function routes to appropriate SQS queue
3. Downstream processors consume from queue-specific SQS queues

## Deployment

The Lambda function is deployed using AWS SAM with:
- MSK trigger configuration
- VPC configuration for MSK access
- IAM roles for SQS and MSK permissions
- Environment-specific configurations

## Monitoring

- CloudWatch metrics for throughput and latency
- X-Ray tracing for performance analysis
- Dead letter queue monitoring
- SQS queue depth monitoring