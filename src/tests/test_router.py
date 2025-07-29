"""
Unit tests for the topic queue router Lambda function.
"""

import json
import base64
import pytest
from unittest.mock import Mock, patch, MagicMock
from router import (
    parse_kafka_message,
    determine_queue_type,
    route_messages_by_queue_type,
    lambda_handler
)


class TestParseKafkaMessage:
    def test_parse_valid_message(self):
        """Test parsing a valid Kafka message."""
        message_data = {"productId": 123, "applicationCount": 75, "queueType": "MEDIUM"}
        encoded_message = base64.b64encode(json.dumps(message_data).encode()).decode()
        
        record = {"value": encoded_message}
        result = parse_kafka_message(record)
        
        assert result == message_data

    def test_parse_empty_message(self):
        """Test parsing an empty message."""
        record = {"value": ""}
        result = parse_kafka_message(record)
        
        assert result is None

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        invalid_json = base64.b64encode(b"invalid json").decode()
        record = {"value": invalid_json}
        
        result = parse_kafka_message(record)
        
        assert result is None


class TestDetermineQueueType:
    def test_existing_queue_type(self):
        """Test when queueType is already set."""
        message = {"queueType": "LARGE", "applicationCount": 150}
        result = determine_queue_type(message)
        
        assert result == "LARGE"

    def test_small_queue_determination(self):
        """Test determination of SMALL queue."""
        message = {"applicationCount": 25}
        result = determine_queue_type(message)
        
        assert result == "SMALL"

    def test_medium_queue_determination(self):
        """Test determination of MEDIUM queue."""
        message = {"applicationCount": 100}
        result = determine_queue_type(message)
        
        assert result == "MEDIUM"

    def test_large_queue_determination(self):
        """Test determination of LARGE queue."""
        message = {"applicationCount": 300}
        result = determine_queue_type(message)
        
        assert result == "LARGE"

    def test_boundary_conditions(self):
        """Test boundary conditions for queue determination."""
        # Test boundary at 50
        assert determine_queue_type({"applicationCount": 50}) == "SMALL"
        assert determine_queue_type({"applicationCount": 51}) == "MEDIUM"
        
        # Test boundary at 200
        assert determine_queue_type({"applicationCount": 200}) == "MEDIUM"
        assert determine_queue_type({"applicationCount": 201}) == "LARGE"


class TestRouteMessagesByQueueType:
    def test_route_mixed_messages(self):
        """Test routing messages of different types."""
        messages = [
            {"productId": 1, "applicationCount": 25},
            {"productId": 2, "applicationCount": 100},
            {"productId": 3, "applicationCount": 300}
        ]
        
        result = route_messages_by_queue_type(messages)
        
        assert len(result["SMALL"]) == 1
        assert len(result["MEDIUM"]) == 1
        assert len(result["LARGE"]) == 1
        assert result["SMALL"][0]["queueType"] == "SMALL"
        assert result["MEDIUM"][0]["queueType"] == "MEDIUM"
        assert result["LARGE"][0]["queueType"] == "LARGE"


class TestLambdaHandler:
    @patch.dict('os.environ', {
        'SMALL_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-small-products-queue',
        'MEDIUM_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-medium-products-queue',
        'LARGE_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-large-products-queue'
    })
    @patch('router.sqs_client')
    def test_lambda_handler_success(self, mock_sqs_client):
        """Test successful Lambda handler execution."""
        # Mock SQS client
        mock_sqs_client.send_message_batch.return_value = {'Failed': []}
        
        # Create test event
        message_data = {"productId": 123, "applicationCount": 75}
        encoded_message = base64.b64encode(json.dumps(message_data).encode()).decode()
        
        event = {
            "records": {
                "product-applications-updates-dev-0": [
                    {"value": encoded_message}
                ]
            }
        }
        
        context = Mock()
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert result["processedMessages"] == 1
        assert result["queueDistribution"]["medium"] == 1

    @patch.dict('os.environ', {
        'SMALL_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-small-products-queue',
        'MEDIUM_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-medium-products-queue',
        'LARGE_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-large-products-queue'
    })
    def test_lambda_handler_empty_event(self):
        """Test Lambda handler with empty event."""
        event = {"records": {}}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert result["processedMessages"] == 0

    @patch.dict('os.environ', {
        'SMALL_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-small-products-queue',
        'MEDIUM_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-medium-products-queue',
        'LARGE_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/dev-large-products-queue'
    })
    def test_lambda_handler_exception(self):
        """Test Lambda handler with exception."""
        # Create invalid event that will cause an exception
        event = None
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 500
        assert "error" in result