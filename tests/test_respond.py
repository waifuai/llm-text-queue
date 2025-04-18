import pytest
from unittest.mock import patch, MagicMock
from src import respond
import google.generativeai as genai # Import genai for mocking

def test_predict_response():
    """Test predict_response with a mocked Gemini API call."""
    test_prompt = "test prompt"
    expected_response = "test reply"

    # Mock the genai.GenerativeModel and its generate_content method
    with patch('src.respond.genai.GenerativeModel') as mock_generative_model:
        mock_model_instance = MagicMock()
        mock_generative_model.return_value = mock_model_instance
        
        mock_response = MagicMock()
        mock_response.text = expected_response
        mock_response.candidates = [MagicMock()] # Simulate a valid response
        mock_response.candidates[0].content.parts = [MagicMock()]

        mock_model_instance.generate_content.return_value = mock_response

        response = respond.predict_response(test_prompt)

        assert response == expected_response
        mock_generative_model.assert_called_once_with('gemini-2.5-flash-preview-04-17') # Check model name
        mock_model_instance.generate_content.assert_called_once_with(test_prompt)

def test_predict_response_api_error():
    """Test predict_response when Gemini API call fails."""
    test_prompt = "test prompt"

    with patch('src.respond.genai.GenerativeModel') as mock_generative_model:
        mock_model_instance = MagicMock()
        mock_generative_model.return_value = mock_model_instance
        
        mock_model_instance.generate_content.side_effect = Exception("API error")

        response = respond.predict_response(test_prompt)

        assert response == "Error generating AI response."
        mock_generative_model.assert_called_once_with('gemini-2.5-flash-preview-04-17')
        mock_model_instance.generate_content.assert_called_once_with(test_prompt)

def test_predict_response_blocked():
    """Test predict_response when Gemini response is blocked."""
    test_prompt = "test prompt"

    with patch('src.respond.genai.GenerativeModel') as mock_generative_model:
        mock_model_instance = MagicMock()
        mock_generative_model.return_value = mock_model_instance
        
        mock_response = MagicMock()
        mock_response.candidates = [] # Simulate a blocked response
        mock_response.prompt_feedback.block_reason = "safety"

        mock_model_instance.generate_content.return_value = mock_response

        response = respond.predict_response(test_prompt)

        assert response == "AI response generation failed or was blocked."
        mock_generative_model.assert_called_once_with('gemini-2.5-flash-preview-04-17')
        mock_model_instance.generate_content.assert_called_once_with(test_prompt)