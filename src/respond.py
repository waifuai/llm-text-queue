# src/respond.py
# Core generation service using Google GenAI SDK.

import logging
from typing import Optional

from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration
from config import MAX_NEW_TOKENS, GEMINI_API_KEY, MODEL_NAME

# Import new Google GenAI SDK
from google import genai

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize GenAI Client
client: Optional[genai.Client] = None
if not GEMINI_API_KEY:
    logging.error("API key not found in env or ~/.api-gemini.")
else:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logging.info("Google GenAI client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Google GenAI client: {e}")
        client = None

# This function predicts the response for a given prompt using the Gemini API.
def predict_response(prompt: str):
    """
    Generates a response for a given prompt using the configured Gemini model.

    Args:
        prompt: The input prompt string.

    Returns:
        The generated text response, or an error message string if generation fails.
    """
    logging.info(f"Received prompt: {prompt}")
    if not client:
        logging.error("GenAI client is not available.")
        return "Error: AI model not configured."

    # Check if it's a test prompt
    is_test_prompt = prompt.startswith("test prompt:")
    # Strip the prefix for the actual API call
    api_prompt = prompt[len("test prompt:"):] if is_test_prompt else prompt

    result_text = ""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=api_prompt,
            generation_config={"max_output_tokens": MAX_NEW_TOKENS},
        )

        if not getattr(response, "candidates", None):
            logging.warning("GenAI response has no candidates.")
            result_text = "AI response generation failed or was blocked."
        else:
            result_text = getattr(response, "text", "") or "AI response generation failed or was blocked."

        logging.info(f"Generated response: {result_text}")

    except Exception as e:
        logging.error(f"Error during GenAI API call: {e}")
        result_text = "Error generating AI response."

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