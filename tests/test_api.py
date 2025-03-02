import pytest
import requests

@pytest.fixture
def base_url():
    return "http://localhost:5000"

def test_health_check(base_url):
    response = requests.get(f"{base_url}/health")
    assert response.status_code == 200
    assert response.text == "Services healthy"

def test_text_generation(base_url):
    test_prompt = "Hello"
    response = requests.post(
        f"{base_url}/generate",
        json={"prompt": test_prompt}
    )
    assert response.status_code == 200
    assert "response" in response.json()
    assert len(response.json()["response"]) > 0