# tests/conftest.py
import os
import sys
import pytest
from unittest.mock import patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

@pytest.fixture(autouse=True)
def reset_config():
    """Reset configuration before each test to avoid state contamination."""
    # This fixture runs automatically before each test
    # to ensure clean configuration state
    yield
    # Any cleanup can go here

@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing."""
    with patch('redis.from_url') as mock_redis:
        mock_conn = mock_redis.return_value
        mock_conn.ping.return_value = True
        mock_conn.info.return_value = {"redis_version": "7.0.0"}
        yield mock_conn

@pytest.fixture
def mock_queue():
    """Mock RQ queue for testing."""
    with patch('main.redis_queue') as mock_queue:
        mock_queue.name = 'test_queue'
        yield mock_queue

@pytest.fixture
def clean_environment():
    """Provide a clean environment for testing."""
    original_env = os.environ.copy()
    os.environ.clear()

    # Set minimal required environment variables for tests
    os.environ.update({
        'REDIS_URL': 'redis://localhost:6379',
        'QUEUE_PORT': '5000',
        'RESPOND_PORT': '5001',
        'PORT': '8000',
        'MAX_NEW_TOKENS': '150'
    })

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def mock_openrouter_api():
    """Mock OpenRouter API responses."""
    with patch('provider_openrouter.requests.post') as mock_post:
        def mock_response(*args, **kwargs):
            mock_resp = type('MockResponse', (), {})()
            mock_resp.status_code = 200
            mock_resp.json = lambda: {
                "choices": [
                    {
                        "message": {
                            "content": "Mock OpenRouter response"
                        }
                    }
                ]
            }
            mock_resp.text = "Mock response"
            return mock_resp

        mock_post.return_value = mock_response()
        yield mock_post