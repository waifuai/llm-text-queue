# tests/test_providers.py
import pytest
from unittest.mock import patch, MagicMock, mock_open

# Import provider modules
import sys
sys.path.insert(0, 'src')
from provider_openrouter import (
    generate_with_openrouter,
    _resolve_openrouter_api_key,
    _to_messages,
    OPENROUTER_API_URL
)


class TestOpenRouterProvider:
    """Test suite for OpenRouter provider."""

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_success(self, mock_post, mock_resolve_key):
        """Test successful OpenRouter generation."""
        # Mock API key resolution
        mock_resolve_key.return_value = "test_api_key"

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Generated response"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        result = generate_with_openrouter("Test prompt")

        assert result == "Generated response"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['headers']['Authorization'] == 'Bearer test_api_key'
        assert call_args[1]['json']['messages'][0]['role'] == 'user'
        assert call_args[1]['json']['messages'][0]['content'] == 'Test prompt'

    @patch('provider_openrouter._resolve_openrouter_api_key')
    def test_generate_with_openrouter_no_api_key(self, mock_resolve_key):
        """Test OpenRouter generation with no API key."""
        mock_resolve_key.return_value = None

        result = generate_with_openrouter("Test prompt")

        assert result is None

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_api_error(self, mock_post, mock_resolve_key):
        """Test OpenRouter generation with API error."""
        mock_resolve_key.return_value = "test_api_key"

        # Mock API error response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        result = generate_with_openrouter("Test prompt")

        assert result is None

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_no_choices(self, mock_post, mock_resolve_key):
        """Test OpenRouter generation with no choices in response."""
        mock_resolve_key.return_value = "test_api_key"

        # Mock response with no choices
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}
        mock_post.return_value = mock_response

        result = generate_with_openrouter("Test prompt")

        assert result is None

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_empty_content(self, mock_post, mock_resolve_key):
        """Test OpenRouter generation with empty content."""
        mock_resolve_key.return_value = "test_api_key"

        # Mock response with empty content
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        result = generate_with_openrouter("Test prompt")

        assert result is None

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_exception(self, mock_post, mock_resolve_key):
        """Test OpenRouter generation with request exception."""
        mock_resolve_key.return_value = "test_api_key"

        # Mock request exception
        mock_post.side_effect = Exception("Network error")

        result = generate_with_openrouter("Test prompt")

        assert result is None

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'env_api_key'}, clear=True)
    def test_resolve_openrouter_api_key_from_env(self):
        """Test resolving OpenRouter API key from environment."""
        result = _resolve_openrouter_api_key()
        assert result == 'env_api_key'

    @patch.dict('os.environ', {}, clear=True)
    @patch('builtins.open', new_callable=mock_open, read_data='file_api_key')
    @patch('os.path.exists')
    def test_resolve_openrouter_api_key_from_file(self, mock_exists, mock_file):
        """Test resolving OpenRouter API key from file."""
        mock_exists.return_value = True

        result = _resolve_openrouter_api_key()
        assert result == 'file_api_key'

    @patch.dict('os.environ', {}, clear=True)
    @patch('os.path.exists')
    def test_resolve_openrouter_api_key_not_found(self, mock_exists):
        """Test resolving OpenRouter API key when not found."""
        mock_exists.return_value = False

        result = _resolve_openrouter_api_key()
        assert result is None

    def test_to_messages(self):
        """Test converting prompt to messages format."""
        result = _to_messages("Test prompt")

        expected = [
            {
                "role": "user",
                "content": "Test prompt"
            }
        ]

        assert result == expected

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_custom_params(self, mock_post, mock_resolve_key):
        """Test OpenRouter generation with custom parameters."""
        mock_resolve_key.return_value = "test_api_key"

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Custom response"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        result = generate_with_openrouter(
            prompt="Custom prompt",
            model_name="custom-model",
            max_new_tokens=500,
            timeout=30
        )

        assert result == "Custom response"

        # Verify the request was made with correct parameters
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        assert request_data['model'] == 'custom-model'
        assert request_data['max_tokens'] == 500
        assert call_args[1]['timeout'] == 30

    @patch('provider_openrouter._resolve_openrouter_api_key')
    @patch('provider_openrouter.requests.post')
    def test_generate_with_openrouter_temperature_setting(self, mock_post, mock_resolve_key):
        """Test that OpenRouter uses the correct temperature setting."""
        mock_resolve_key.return_value = "test_api_key"

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Temperature response"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        result = generate_with_openrouter("Test prompt", temperature=0.7)

        # Verify temperature was set in request
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        assert request_data['temperature'] == 0.7


class TestProviderIntegration:
    """Test suite for provider integration and fallback logic."""

    @patch('main.PROVIDER', 'openrouter')
    @patch('main.predict_response')
    def test_provider_selection_openrouter(self, mock_predict):
        """Test that openrouter provider is selected correctly."""
        from main import app

        mock_predict.return_value = "OpenRouter response"

        with app.test_client() as client:
            response = client.post('/generate', json={"prompt": "Test"})
            assert response.status_code == 200
            data = response.json()
            assert data['provider_used'] == 'openrouter'

    @patch('main.PROVIDER', 'gemini')
    @patch('main._generate_with_gemini')
    def test_provider_selection_gemini(self, mock_gemini):
        """Test that gemini provider is selected correctly."""
        mock_gemini.return_value = "Gemini response"

        from main import app

        with app.test_client() as client:
            response = client.post('/generate', json={"prompt": "Test"})
            assert response.status_code == 200
            data = response.json()
            assert data['provider_used'] == 'gemini'