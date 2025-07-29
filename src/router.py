"""
High-performance Kafka to SQS router for Marketring queue management.

This Lambda function consumes messages from MSK and routes them to appropriate
SQS queues based on queue type metadata from ProductApplicationsCountTransform.
"""

import json
import os
import base64
import boto3
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize SQS client (reused across invocations)
sqs_client = boto3.client('sqs')

# Queue URL mappings from environment variables
QUEUE_MAPPINGS = {
    'SMALL': os.environ['SMALL_QUEUE_URL'],
    'MEDIUM': os.environ['MEDIUM_QUEUE_URL'],
    'LARGE': os.environ['LARGE_QUEUE_URL']
}

# Performance configuration
MAX_WORKERS = 10  # Concurrent SQS operations
BATCH_SIZE = 10   # SQS batch send size


class RouterMetrics:
    """Centralized metrics tracking for the router."""
    
    @staticmethod
    def record_message_processed(queue_type: str):
        metrics.add_metric(name="MessagesProcessed", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="queue_type", value=queue_type)
    
    @staticmethod
    def record_routing_error(error_type: str):
        metrics.add_metric(name="RoutingErrors", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="error_type", value=error_type)
    
    @staticmethod
    def record_batch_size(size: int):
        metrics.add_metric(name="BatchSize", unit=MetricUnit.Count, value=size)


def parse_kafka_message(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse Kafka message from MSK event record.
    
    Args:
        record: MSK event record containing Kafka message
        
    Returns:
        Parsed message data or None if parsing fails
    """
    try:
        # Decode base64 encoded message value
        encoded_value = record.get('value', '')
        if not encoded_value:
            logger.warning("Empty message value in record", extra={"record": record})
            return None
            
        # Decode from base64
        decoded_bytes = base64.b64decode(encoded_value)
        message_str = decoded_bytes.decode('utf-8')
        
        # Parse JSON
        message_data = json.loads(message_str)
        
        logger.debug("Parsed message", extra={"message": message_data})
        return message_data
        
    except Exception as e:
        logger.error("Failed to parse Kafka message", extra={
            "error": str(e),
            "record": record
        })
        RouterMetrics.record_routing_error("parse_error")
        return None


def determine_queue_type(message: Dict[str, Any]) -> Optional[str]:
    """
    Determine target queue type from message metadata.
    
    Args:
        message: Parsed message data
        
    Returns:
        Queue type (SMALL, MEDIUM, LARGE) or None if undetermined
    """
    # First, check if ProductApplicationsCountTransform already set queueType
    queue_type = message.get('queueType')
    if queue_type and queue_type in QUEUE_MAPPINGS:
        return queue_type
    
    # Fallback: determine from applicationCount if queueType is missing
    app_count = message.get('applicationCount', message.get('NumberOfApplications', 0))
    
    if app_count <= 50:
        return 'SMALL'
    elif app_count <= 200:
        return 'MEDIUM'
    else:
        return 'LARGE'


def send_to_sqs_batch(messages: List[Dict[str, Any]], queue_url: str) -> bool:
    """
    Send messages to SQS in batch for optimal performance.
    
    Args:
        messages: List of messages to send
        queue_url: Target SQS queue URL
        
    Returns:
        True if all messages sent successfully, False otherwise
    """
    try:
        # Prepare batch entries
        entries = []
        for i, message in enumerate(messages):
            entries.append({
                'Id': str(i),
                'MessageBody': json.dumps(message),
                'MessageAttributes': {
                    'queueType': {
                        'StringValue': message.get('queueType', 'UNKNOWN'),
                        'DataType': 'String'
                    },
                    'productId': {
                        'StringValue': str(message.get('productId', 'unknown')),
                        'DataType': 'String'
                    }
                }
            })
        
        # Send batch to SQS
        response = sqs_client.send_message_batch(
            QueueUrl=queue_url,
            Entries=entries
        )
        
        # Check for failures
        if 'Failed' in response and response['Failed']:
            logger.error("SQS batch send failures", extra={
                "failed_messages": response['Failed'],
                "queue_url": queue_url
            })
            RouterMetrics.record_routing_error("sqs_batch_failure")
            return False
            
        logger.info("Successfully sent batch to SQS", extra={
            "queue_url": queue_url,
            "message_count": len(messages)
        })
        return True
        
    except Exception as e:
        logger.error("Failed to send batch to SQS", extra={
            "error": str(e),
            "queue_url": queue_url,
            "message_count": len(messages)
        })
        RouterMetrics.record_routing_error("sqs_send_error")
        return False


def route_messages_by_queue_type(parsed_messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group messages by their target queue type.
    
    Args:
        parsed_messages: List of parsed message data
        
    Returns:
        Dictionary mapping queue types to their messages
    """
    grouped_messages = {'SMALL': [], 'MEDIUM': [], 'LARGE': []}
    
    for message in parsed_messages:
        queue_type = determine_queue_type(message)
        if queue_type and queue_type in grouped_messages:
            # Ensure queueType is set in message for downstream processing
            message['queueType'] = queue_type
            grouped_messages[queue_type].append(message)
            RouterMetrics.record_message_processed(queue_type)
        else:
            logger.warning("Unable to determine queue type", extra={"message": message})
            RouterMetrics.record_routing_error("undetermined_queue_type")
    
    return grouped_messages


def send_batches_concurrently(grouped_messages: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    Send message batches to SQS queues concurrently for optimal performance.
    
    Args:
        grouped_messages: Messages grouped by queue type
        
    Returns:
        True if all batches sent successfully, False otherwise
    """
    all_successful = True
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        
        for queue_type, messages in grouped_messages.items():
            if not messages:
                continue
                
            queue_url = QUEUE_MAPPINGS[queue_type]
            
            # Split into batches of BATCH_SIZE (SQS limit is 10 messages per batch)
            for i in range(0, len(messages), BATCH_SIZE):
                batch = messages[i:i + BATCH_SIZE]
                future = executor.submit(send_to_sqs_batch, batch, queue_url)
                futures.append((future, queue_type, len(batch)))
        
        # Wait for all batches to complete
        for future, queue_type, batch_size in futures:
            try:
                success = future.result(timeout=30)  # 30 second timeout per batch
                if not success:
                    all_successful = False
                else:
                    RouterMetrics.record_batch_size(batch_size)
            except Exception as e:
                logger.error("Batch send failed", extra={
                    "error": str(e),
                    "queue_type": queue_type,
                    "batch_size": batch_size
                })
                all_successful = False
                RouterMetrics.record_routing_error("concurrent_send_error")
    
    return all_successful


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for MSK event processing.
    
    Args:
        event: MSK event containing Kafka records
        context: Lambda context object
        
    Returns:
        Response indicating processing status
    """
    try:
        logger.info("Processing MSK event", extra={
            "event_source": event.get('eventSource'),
            "record_count": len(event.get('records', {}))
        })
        
        # Parse all Kafka messages from the event
        parsed_messages = []
        total_records = 0
        
        for topic_partition, records in event.get('records', {}).items():
            total_records += len(records)
            logger.debug("Processing partition", extra={
                "topic_partition": topic_partition,
                "record_count": len(records)
            })
            
            for record in records:
                parsed_message = parse_kafka_message(record)
                if parsed_message:
                    parsed_messages.append(parsed_message)
        
        logger.info("Parsed messages from MSK", extra={
            "total_records": total_records,
            "parsed_messages": len(parsed_messages)
        })
        
        if not parsed_messages:
            logger.warning("No valid messages to process")
            return {"statusCode": 200, "processedMessages": 0}
        
        # Group messages by target queue type
        grouped_messages = route_messages_by_queue_type(parsed_messages)
        
        logger.info("Grouped messages by queue type", extra={
            "small_count": len(grouped_messages['SMALL']),
            "medium_count": len(grouped_messages['MEDIUM']),
            "large_count": len(grouped_messages['LARGE'])
        })
        
        # Send messages to SQS queues concurrently
        success = send_batches_concurrently(grouped_messages)
        
        response = {
            "statusCode": 200 if success else 500,
            "processedMessages": len(parsed_messages),
            "queueDistribution": {
                "small": len(grouped_messages['SMALL']),
                "medium": len(grouped_messages['MEDIUM']),
                "large": len(grouped_messages['LARGE'])
            }
        }
        
        logger.info("Completed message routing", extra=response)
        return response
        
    except Exception as e:
        logger.error("Lambda handler error", extra={"error": str(e)})
        RouterMetrics.record_routing_error("handler_error")
        return {
            "statusCode": 500,
            "error": str(e)
        }