import pytest
import requests
from unittest.mock import patch

@pytest.fixture
def base_url():
    return "http://localhost:5000"

def test_health_check(base_url):
    response = requests.get(f"{base_url}/health")
    assert response.status_code == 200
    assert response.text == "Services healthy"

    # Test Redis unavailable
    with patch('src.queue.conn.ping', side_effect=Exception("Redis unavailable")):
        response = requests.get(f"{base_url}/health")
        assert response.status_code == 503
        assert response.text == "Service unavailable"

    # Test GPU service unavailable
    with patch('src.queue.requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("GPU service unavailable")
        response = requests.get(f"{base_url}/health")
        assert response.status_code == 503
        assert response.text == "Service unavailable"

def test_text_generation(base_url):
    # Test with a normal prompt
    test_prompt = "Hello"
    response = requests.post(
        f"{base_url}/generate",
        json={"prompt": test_prompt}
    )
    assert response.status_code == 200
    assert "response" in response.json()
    assert len(response.json()["response"]) > 0

    # Test with an empty prompt
    test_prompt = ""
    response = requests.post(
        f"{base_url}/generate",
        json={"prompt": test_prompt}
    )
    assert response.status_code == 200
    assert "response" in response.json()
    assert len(response.json()["response"]) > 0

    # Test with a long prompt
    test_prompt = "This is a very long prompt. " * 100
    response = requests.post(
        f"{base_url}/generate",
        json={"prompt": test_prompt}
    )
    assert response.status_code == 200
    assert "response" in response.json()
    assert len(response.json()["response"]) > 0

    # Test with special characters
    test_prompt = "!@#$%^&*()"
    response = requests.post(
        f"{base_url}/generate",
        json={"prompt": test_prompt}
    )
    assert response.status_code == 200
    assert "response" in response.json()
    assert len(response.json()["response"]) > 0