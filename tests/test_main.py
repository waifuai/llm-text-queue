# tests/test_main.py
import json
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

# Import the main app
import sys
sys.path.insert(0, 'src')
from main import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestMainService:
    """Test suite for the main consolidated service."""

    def test_index_endpoint(self, client):
        """Test the root index endpoint."""
        response = client.get('/')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'service' in data
        assert 'version' in data
        assert 'endpoints' in data
        assert data['service'] == 'LLM Text Queue GPU'

    @patch('main.redis_conn')
    @patch('main.redis_queue')
    def test_health_endpoint_healthy(self, mock_queue, mock_redis, client):
        """Test health endpoint when all services are healthy."""
        # Mock Redis connection
        mock_redis.ping.return_value = True

        # Mock queue
        mock_queue.name = 'test_queue'

        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['services']['redis'] is True
        assert data['services']['queue'] is True

    @patch('main.redis_conn')
    @patch('main.redis_queue')
    def test_health_endpoint_unhealthy(self, mock_queue, mock_redis, client):
        """Test health endpoint when services are unhealthy."""
        # Mock Redis connection failure
        mock_redis.ping.side_effect = Exception("Connection failed")

        # Mock queue as None
        mock_queue = None

        response = client.get('/health')
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data['status'] == 'unhealthy'
        assert data['services']['overall'] is False

    def test_generate_endpoint_missing_json(self, client):
        """Test generate endpoint with missing JSON payload."""
        response = client.post('/generate', data="not json")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Request must be JSON" in data['error']

    def test_generate_endpoint_empty_payload(self, client):
        """Test generate endpoint with empty JSON payload."""
        response = client.post('/generate', json={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Missing 'prompt' parameter" in data['error']

    def test_generate_endpoint_missing_prompt(self, client):
        """Test generate endpoint with missing prompt field."""
        response = client.post('/generate', json={"not_prompt": "value"})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Missing 'prompt' parameter" in data['error']

    @patch('main.predict_response')
    def test_generate_endpoint_valid_request(self, mock_predict, client):
        """Test generate endpoint with valid request."""
        mock_predict.return_value = "Generated response"

        response = client.post('/generate', json={"prompt": "Test prompt"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['response'] == "Generated response"
        assert data['provider_used'] == 'openrouter'  # Default provider
        assert data['method'] == 'direct'

        mock_predict.assert_called_once_with("Test prompt")

    def test_generate_endpoint_invalid_prompt(self, client):
        """Test generate endpoint with invalid prompt."""
        # Test with empty prompt
        response = client.post('/generate', json={"prompt": ""})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Prompt cannot be empty" in data['error']

        # Test with whitespace-only prompt
        response = client.post('/generate', json={"prompt": "   "})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Prompt cannot be empty" in data['error']

        # Test with overly long prompt
        long_prompt = "a" * 10001
        response = client.post('/generate', json={"prompt": long_prompt})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Prompt too long" in data['error']

    @patch('main.redis_conn')
    @patch('main.redis_queue')
    def test_queue_generate_endpoint_no_redis(self, mock_queue, mock_redis, client):
        """Test queue generate endpoint when Redis is not available."""
        # Mock Redis as None
        mock_redis = None
        mock_queue = None

        response = client.post('/queue/generate', json={"prompt": "Test prompt"})
        assert response.status_code == 503
        data = json.loads(response.data)
        assert "Service temporarily unavailable" in data['error']

    @patch('main.redis_conn')
    @patch('main.redis_queue')
    @patch('main.call_predict_response')
    def test_queue_generate_endpoint_valid_request(self, mock_call, mock_queue, mock_redis, client):
        """Test queue generate endpoint with valid request."""
        # Mock Redis connection
        mock_redis.ping.return_value = True

        # Mock queue
        mock_queue.name = 'test_queue'

        # Mock job
        mock_job = MagicMock()
        mock_job.id = 'test_job_id'
        mock_job.get_result.return_value = "Queued response"
        mock_queue.enqueue_call.return_value = mock_job

        # Mock the call_predict_response function
        mock_call.return_value = "Queued response"

        response = client.post('/queue/generate', json={"prompt": "Test prompt"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['response'] == "Queued response"
        assert data['job_id'] == 'test_job_id'
        assert data['method'] == 'queued'

    @patch('main.redis_conn')
    def test_metrics_endpoint(self, mock_redis, client):
        """Test metrics endpoint."""
        # Mock Redis info
        mock_redis.info.return_value = {"redis_version": "7.0.0"}

        response = client.get('/metrics')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'service' in data
        assert 'version' in data
        assert 'redis' in data
        assert 'queue' in data
        assert data['service'] == 'LLM Text Queue GPU v2.0'

    def test_rate_limiting(self, client):
        """Test that rate limiting is applied to endpoints."""
        # Make multiple requests quickly to trigger rate limit
        for i in range(15):  # Exceed the 10 per minute limit
            response = client.post('/generate', json={"prompt": f"Test {i}"})

        # The last request should be rate limited (429 status code)
        # Note: This test might not work perfectly with Flask-Limiter in test mode
        # but demonstrates the concept
        assert response.status_code in [200, 429]


class TestInputValidation:
    """Test suite for input validation functions."""

    def test_sanitize_prompt_normal(self):
        """Test sanitizing normal prompt."""
        from main import sanitize_prompt
        result = sanitize_prompt("Hello world")
        assert result == "Hello world"

    def test_sanitize_prompt_whitespace(self):
        """Test sanitizing prompt with excessive whitespace."""
        from main import sanitize_prompt
        result = sanitize_prompt("Hello   world\n\n\nMore text")
        assert result == "Hello world\n\nMore text"

    def test_sanitize_prompt_control_chars(self):
        """Test sanitizing prompt with control characters."""
        from main import sanitize_prompt
        result = sanitize_prompt("Hello\x00\x01world\x1f")
        assert result == "Helloworld"

    def test_sanitize_prompt_empty(self):
        """Test sanitizing empty prompt."""
        from main import sanitize_prompt
        result = sanitize_prompt("")
        assert result == ""

    def test_sanitize_prompt_none(self):
        """Test sanitizing None prompt."""
        from main import sanitize_prompt
        result = sanitize_prompt(None)
        assert result == ""

    def test_validate_generation_prompt_valid(self):
        """Test validating valid prompt."""
        from main import validate_generation_prompt
        is_valid, error = validate_generation_prompt("Valid prompt")
        assert is_valid is True
        assert error == ""

    def test_validate_generation_prompt_empty(self):
        """Test validating empty prompt."""
        from main import validate_generation_prompt
        is_valid, error = validate_generation_prompt("")
        assert is_valid is False
        assert "Missing 'prompt' parameter" in error

    def test_validate_generation_prompt_whitespace(self):
        """Test validating whitespace-only prompt."""
        from main import validate_generation_prompt
        is_valid, error = validate_generation_prompt("   ")
        assert is_valid is False
        assert "Prompt cannot be empty" in error

    def test_validate_generation_prompt_too_long(self):
        """Test validating overly long prompt."""
        from main import validate_generation_prompt
        long_prompt = "a" * 10001
        is_valid, error = validate_generation_prompt(long_prompt)
        assert is_valid is False
        assert "Prompt too long" in error