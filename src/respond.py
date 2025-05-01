# src/respond.py
# This file contains the core chatbot logic. It loads the distilgpt2 model, processes incoming prompts, and generates responses.

import os
import google.generativeai as genai
from flask import Flask, request, jsonify
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration
from config import MAX_NEW_TOKENS, GEMINI_API_KEY

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configure Gemini API
if not GEMINI_API_KEY:
    logging.error("GEMINI_API_KEY not found in ~/.api-gemini.")
    gemini_model = None # Indicate model is unavailable
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-2.5-pro-preview-03-25')
        logging.info("Gemini API configured successfully.")
    except Exception as e:
        logging.error(f"Error configuring Gemini API: {e}")
        gemini_model = None

# Set generation config
generation_config = genai.types.GenerationConfig(max_output_tokens=MAX_NEW_TOKENS)

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

    # Check if it's a test prompt
    is_test_prompt = prompt.startswith("test prompt:")
    if is_test_prompt:
        # Remove the prefix for the actual API call
        api_prompt = prompt[len("test prompt:"):]
    else:
        api_prompt = prompt

    result = "" # Variable to hold the core result

    try:
        # TODO: Add safety_settings and generation_config if needed
        # generation_config = genai.types.GenerationConfig(max_output_tokens=MAX_NEW_TOKENS)
        response = gemini_model.generate_content(api_prompt)
        # Check for potential blocks or errors in the response
        if not response.candidates or not response.candidates[0].content.parts:
             logging.warning(f"Gemini response blocked or empty. Finish reason: {response.prompt_feedback.block_reason if response.prompt_feedback else 'N/A'}")
             # Assign blocked message to result
             result = "AI response generation failed or was blocked."
        else:
            result = response.text

        logging.info(f"Generated response: {result}")

    except Exception as e:
        logging.error(f"Error during Gemini API call: {e}")
        # Assign error message to result
        result = "Error generating AI response."

    # Apply test prompt logic to the final result
    if is_test_prompt:
        return result # Return only the result for test prompts
    else:
        # Add conversational text for non-test prompts
        return f"Okay. I received \"{prompt}\".\n\n{result}"

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