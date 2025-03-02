# src/queue.py
# This file defines the queue service, which receives prompts, queues them using Redis, and sends them to respond.py for processing.

import subprocess
import requests
import logging

from flask import Flask, request, jsonify
from rq import Queue
from worker import conn

from config import GPU_SERVICE_URL

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
q = Queue(connection=conn)


# This function calls the GPU service to generate a response for a given prompt.
def call_predict_response(prompt):
    try:
        response = requests.post(f"{GPU_SERVICE_URL}/generate", json={'prompt': prompt})
        response.raise_for_status()
        return response.json()['response']
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling GPU service: {e}")
        return "Error: Could not connect to the GPU service."


# This function is used for testing the worker.
def test_worker():
    # Returns a simple string to test the worker.
    return "test worker"


# This function checks the health of the services.
def check_services_health():
    try:
        # Check if Redis is running
        conn.ping()

        # Check if worker is running by enqueueing a test job
        job = q.enqueue_call(func=test_worker, result_ttl=5)
        job.get_status()
        job.delete()

        # Check if GPU service is running
        response = requests.get(GPU_SERVICE_URL)
        response.raise_for_status()
    except (subprocess.CalledProcessError, requests.exceptions.RequestException, redis.exceptions.ConnectionError) as e:
        logging.error(f"Service health check failed: {e}")
        return False
    return True


# This endpoint checks the health of the services.
@app.route('/health')
def health_check():
    if check_services_health():
        return 'Services healthy', 200
    else:
        return 'Service unavailable', 503


# This endpoint generates text based on the provided prompt.
@app.route('/generate', methods=['POST'])
def generate_text():
    prompt = request.json.get('prompt')
    if not prompt:
        return jsonify({"error": "Missing 'prompt' parameter"}), 400

    job = q.enqueue_call(func=call_predict_response, args=(prompt,), result_ttl=3600) # Reduced result_ttl to 1 hour

    try:
        result = job.get_result(timeout=600)
        return jsonify({"response": result}), 200
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return jsonify({"error": "Error processing request"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0')