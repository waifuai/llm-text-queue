# src/respond.py
# Core generation service with OpenRouter default provider and Gemini fallback.

import logging
from typing import Optional

from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration
from config import MAX_NEW_TOKENS, GEMINI_API_KEY, MODEL_NAME, PROVIDER

# OpenRouter provider module
from provider_openrouter import generate_with_openrouter

# Google GenAI SDK (fallback)
from google import genai

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize Gemini client (fallback path)
gemini_client: Optional[genai.Client] = None
if not GEMINI_API_KEY:
    logging.info("Gemini API key not found in env or ~/.api-gemini; Gemini fallback disabled.")
else:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logging.info("Google GenAI client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Google GenAI client: {e}")
        gemini_client = None

def _generate_with_gemini(prompt: str) -> str:
    if not gemini_client:
        return "Error: AI model not configured."
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            generation_config={"max_output_tokens": MAX_NEW_TOKENS},
        )
        if not getattr(response, "candidates", None):
            return "AI response generation failed or was blocked."
        return getattr(response, "text", "") or "AI response generation failed or was blocked."
    except Exception as e:
        logging.error(f"Error during GenAI API call: {e}")
        return "Error generating AI response."

# This function predicts the response for a given prompt using OpenRouter by default, with Gemini fallback.
def predict_response(prompt: str) -> str:
    """
    Generates a response for a given prompt using the configured provider/model.

    Returns:
        The generated text response, or an error message string if generation fails.
    """
    logging.info(f"Received prompt: {prompt}")

    # Check if it's a test prompt; strip prefix before model call but return bare text in tests
    is_test_prompt = prompt.startswith("test prompt:")
    api_prompt = prompt[len("test prompt:"):] if is_test_prompt else prompt

    result_text = ""

    if PROVIDER == "openrouter":
        # Primary: OpenRouter
        result_text = generate_with_openrouter(api_prompt, model_name=MODEL_NAME, max_new_tokens=MAX_NEW_TOKENS) or ""
        if not result_text:
            logging.warning("OpenRouter generation failed; attempting Gemini fallback.")
            result_text = _generate_with_gemini(api_prompt)
    else:
        # Primary: Gemini
        result_text = _generate_with_gemini(api_prompt)
        if not result_text:
            logging.warning("Gemini generation failed; attempting OpenRouter fallback.")
            result_text = generate_with_openrouter(api_prompt, model_name=MODEL_NAME, max_new_tokens=MAX_NEW_TOKENS) or ""

    if is_test_prompt:
        return result_text
    else:
        return f"Okay. I received \"{prompt}\".\n\n{result_text}"

# This endpoint generates text based on the provided prompt.
@app.route('/generate', methods=['POST'])
def generate_text_endpoint():
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({"error": "Missing 'prompt' parameter"}), 400

    try:
        response = predict_response(prompt)
        return jsonify({"response": response}), 200
    except Exception:
        logging.exception("Error in generate_text_endpoint")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)