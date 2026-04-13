# llm-text-queue

This project provides a simple and efficient text generation service using OpenRouter with a Redis queue for handling requests. It consists of a Flask-based API that exposes endpoints for generating text and checking service health.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Provider Selection and Models](#provider-selection-and-models)
- [Running the Service](#running-the-service)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

*   Text generation using OpenRouter.
*   Request queuing using Redis for handling concurrent requests.
*   Flask API for easy interaction.
*   Health check endpoint for monitoring service status.

## Architecture

The project consists of three main components:

*   `respond.py`: Core text generation service. Uses OpenRouter to handle requests to generate text. Exposes a `/generate` endpoint.
*   `api_queue.py`: Gateway for incoming requests. Receives prompts, queues them using Redis, and forwards them to `respond.py` for processing. Exposes a `/generate` endpoint.
*   `worker.py`: Redis worker that listens for jobs on the queue and executes them for concurrency without blocking.

Request flow:

1. Client sends POST `/generate` to `api_queue.py`.
2. `api_queue.py` enqueues the request via Redis/RQ.
3. `worker.py` picks up the job and calls the GPU service (`respond.py`).
4. `respond.py` generates text using OpenRouter and returns it.
5. `api_queue.py` returns the generated text to the client.

## Prerequisites

*   Python 3.8+
*   uv
*   Redis server (installed and running)
*   Credentials:
    * OpenRouter: `OPENROUTER_API_KEY` or `~/.api-openrouter` (single-line file)

See Redis installation: https://redis.io/docs/getting-started/

## Installation

1. Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd llm-text-queue-gpu
```

2. Create a virtual environment using uv and install tooling inside:

```bash
python -m uv venv .venv
.venv/Scripts/python.exe -m ensurepip
.venv/Scripts/python.exe -m pip install uv
```

3. Install dependencies using uv:

```bash
.venv/Scripts/python.exe -m uv pip install -r requirements.txt
```

Alternatively, you can run the setup helper:

```bash
./src/setup.sh
```

## Configuration

1. Create a `.env` file by copying `.env.example`:

```bash
cp .env.example .env
```

2. Update `.env` values as needed:

* `REDIS_URL`: Redis server URL (default: `redis://localhost:6379`)
* `QUEUE_PORT`: Queue service port (default: `5000`)
* `RESPOND_PORT`: Response service port (default: `5001`)
* `MAX_NEW_TOKENS`: Max new tokens for generation (default: `150`)

Note: Do not commit `.env` to source control.

## Provider Selection and Models

The service uses OpenRouter exclusively. Model is resolved from `OPENROUTER_MODEL_NAME` env or `~/.model-openrouter` (fallback to `openrouter/free`).

Credentials:

* `OPENROUTER_API_KEY` env or `~/.api-openrouter` file containing the key on a single line.

## Running the Service

Start all services using:

```bash
./scripts/start-services.sh
```

The script ensures the uv venv exists, installs dependencies if needed, then starts Redis (if not running), the worker, the queue service, and the response service. Logs are written to `/tmp/*.log` where applicable.

## API Documentation

### Health Check

```http
GET /health
```

Returns 200 if all services are healthy.

### Generate Text

```http
POST /generate
Content-Type: application/json

{
  "prompt": "Your input text here"
}
```

Example Response:

```json
{
  "response": "I am doing well, thank you for asking."
}
```

## Testing

Run the full test suite:

```bash
.venv/Scripts/python.exe -m pytest -q
```

## Troubleshooting

* Missing 'prompt' parameter: Ensure POST body has `{"prompt": "..."}`
* Service unavailable: Check Redis server, worker, API queue and respond services running; review logs in `/tmp/*.log`
* Error generating AI response: Verify OpenRouter credentials are present and valid; check network connectivity

## Contributing

1. Fork the repository.
2. Create a branch for your change.
3. Commit and push your branch.
4. Open a pull request.

## License

This project is licensed under the MIT-0 License - see the [LICENSE](LICENSE) file for details.
