# src/respond.py
# This file contains the core chatbot logic. It loads the distilgpt2 model, processes incoming prompts, and generates responses.

import os
import google.generativeai as genai
from flask import Flask, request, jsonify
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration (MAX_NEW_TOKENS might be removed or adapted later)
from config import MAX_NEW_TOKENS # Keep for now, might adjust usage

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logging.error("GEMINI_API_KEY environment variable not set.")
    # Optionally, raise an error or exit if the key is essential
    # raise ValueError("Missing GEMINI_API_KEY")
    gemini_model = None # Indicate model is unavailable
else:
    try:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        logging.info("Gemini API configured successfully.")
    except Exception as e:
        logging.error(f"Error configuring Gemini API: {e}")
        gemini_model = None

# MAX_NEW_TOKENS from config might be used to set generation config later if needed
# generation_config = genai.types.GenerationConfig(max_output_tokens=MAX_NEW_TOKENS)

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
    if not gemini_model:
        logging.error("Gemini model is not available.")
        return "Error: AI model not configured."

    try:
        # TODO: Add safety_settings and generation_config if needed
        # generation_config = genai.types.GenerationConfig(max_output_tokens=MAX_NEW_TOKENS)
        response = gemini_model.generate_content(prompt)
        # Check for potential blocks or errors in the response
        if not response.candidates or not response.candidates[0].content.parts:
             logging.warning(f"Gemini response blocked or empty. Finish reason: {response.prompt_feedback.block_reason if response.prompt_feedback else 'N/A'}")
             # Consider returning a specific message or the default response
             return "AI response generation failed or was blocked."

        generated_text = response.text
        logging.info(f"Generated response: {generated_text}")
        return generated_text
    except Exception as e:
        logging.error(f"Error during Gemini API call: {e}")
        # Consider returning a more specific error or the default response
        return "Error generating AI response."

# This endpoint generates text based on the provided prompt.
@app.route('/generate', methods=['POST'])
def generate_text_endpoint():
    prompt = request.json.get('prompt')
    if not prompt:
        return jsonify({"error": "Missing 'prompt' parameter"}), 400

    try:
        response = predict_response(prompt)
        return jsonify({"response": response}), 200
    except Exception as e:
        logging.exception("Error in generate_text_endpoint")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)