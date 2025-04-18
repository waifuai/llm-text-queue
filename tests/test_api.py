import pytest
import pytest
import redis # Added for exception patching
from unittest.mock import patch, MagicMock
from src.api_queue import app as flask_app # Import the app instance

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # You might add test-specific configuration here if needed
    # app.config.update({"TESTING": True, ...})
    yield flask_app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

def test_health_check_success(client):
    """Test the /health endpoint when services are healthy."""
    # Mock dependencies called by check_services_health to simulate success
    with patch('src.api_queue.conn.ping', return_value=True) as mock_ping, \
         patch('src.api_queue.q.enqueue_call') as mock_enqueue:

        # Configure mock for enqueue_call and job status/deletion
        mock_job = MagicMock()
        mock_job.get_status.return_value = 'finished' # Or any valid status
        mock_enqueue.return_value = mock_job

        response = client.get("/health")
        assert response.status_code == 200
        assert response.data == b"Services healthy"
        mock_ping.assert_called_once()
        mock_enqueue.assert_called_once()

def test_health_check_redis_unavailable(client):
    """Test the /health endpoint when Redis is unavailable."""
    with patch('src.api_queue.conn.ping', side_effect=redis.exceptions.ConnectionError("Redis unavailable")): # Now redis is imported
        response = client.get("/health")
        assert response.status_code == 503
        assert response.data == b"Service unavailable"

# --- /generate endpoint tests ---

@patch('src.api_queue.q.enqueue_call')
def test_text_generation_success(mock_enqueue_call, client):
    """Test successful text generation via /generate."""
    test_prompt = "Hello"
    expected_response = "Hello there!"

    # Mock the job object and its get_result method
    mock_job = MagicMock()
    mock_job.get_result.return_value = expected_response
    mock_enqueue_call.return_value = mock_job

    response = client.post("/generate", json={"prompt": test_prompt})

    assert response.status_code == 200
    assert response.get_json() == {"response": expected_response}
    # Check that enqueue_call was called correctly
    mock_enqueue_call.assert_called_once()
    args, kwargs = mock_enqueue_call.call_args
    # Check keyword arguments used in enqueue_call
    assert 'func' in kwargs
    assert kwargs['func'].__name__ == 'call_predict_response'
    assert 'args' in kwargs
    assert kwargs['args'][0] == test_prompt # Check the prompt argument within kwargs['args']

@patch('src.api_queue.q.enqueue_call')
def test_text_generation_missing_prompt(mock_enqueue_call, client):
    """Test /generate endpoint when 'prompt' is missing."""
    response = client.post("/generate", json={}) # Missing prompt
    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing 'prompt' parameter"}
    mock_enqueue_call.assert_not_called()

@patch('src.api_queue.q.enqueue_call')
def test_text_generation_job_error(mock_enqueue_call, client):
    """Test /generate endpoint when the RQ job fails."""
    test_prompt = "Hello"

    # Mock the job object to raise an exception on get_result
    mock_job = MagicMock()
    mock_job.get_result.side_effect = Exception("Job failed")
    mock_enqueue_call.return_value = mock_job

    response = client.post("/generate", json={"prompt": test_prompt})

    assert response.status_code == 500
    assert response.get_json() == {"error": "Error processing request"}
    mock_enqueue_call.assert_called_once()

# Add tests for different prompt types (empty, long, special chars) similar to test_text_generation_success
@patch('src.api_queue.q.enqueue_call')
def test_text_generation_empty_prompt(mock_enqueue_call, client):
    test_prompt = ""
    expected_response = "Generated for empty"
    mock_job = MagicMock()
    mock_job.get_result.return_value = expected_response
    mock_enqueue_call.return_value = mock_job
    response = client.post("/generate", json={"prompt": test_prompt})
    # Empty prompt should return 400 according to the application logic
    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing 'prompt' parameter"}

@patch('src.api_queue.q.enqueue_call')
def test_text_generation_long_prompt(mock_enqueue_call, client):
    test_prompt = "This is a very long prompt. " * 100
    expected_response = "Generated for long"
    mock_job = MagicMock()
    mock_job.get_result.return_value = expected_response
    mock_enqueue_call.return_value = mock_job
    response = client.post("/generate", json={"prompt": test_prompt})
    assert response.status_code == 200
    assert response.get_json() == {"response": expected_response}

@patch('src.api_queue.q.enqueue_call')
def test_text_generation_special_chars(mock_enqueue_call, client):
    test_prompt = "!@#$%^&*()"
    expected_response = "Generated for special"
    mock_job = MagicMock()
    mock_job.get_result.return_value = expected_response
    mock_enqueue_call.return_value = mock_job
    response = client.post("/generate", json={"prompt": test_prompt})
    assert response.status_code == 200
    assert response.get_json() == {"response": expected_response}