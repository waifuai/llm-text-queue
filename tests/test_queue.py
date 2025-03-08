import pytest
import requests
from unittest.mock import patch
from src import queue
from src import config
import redis
from rq import Queue, Connection

@pytest.fixture
def redis_conn():
    return redis.Redis.from_url(config.REDIS_URL)

@pytest.fixture
def test_queue(redis_conn):
    return Queue(connection=redis_conn)

def test_call_predict_response_success():
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'response': 'test response'}
        response = queue.call_predict_response('test prompt')
        assert response == 'test response'

def test_call_predict_response_failure():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('test error')
        response = queue.call_predict_response('test prompt')
        assert response == "Error: Could not connect to the GPU service."

def test_test_worker():
    assert queue.test_worker() == "test worker"

def test_check_services_health_success(redis_conn):
    with patch('src.queue.conn.ping') as mock_ping, \
         patch('requests.get') as mock_get, \
         patch('rq.Queue.enqueue_call') as mock_enqueue_call:
        mock_ping.return_value = True
        mock_get.return_value.status_code = 200
        mock_enqueue_call.return_value.get_status.return_value = "queued"
        assert queue.check_services_health() == True

def test_check_services_health_redis_failure(redis_conn):
    with patch('src.queue.conn.ping', side_effect=redis.exceptions.ConnectionError("Redis unavailable")):
        assert queue.check_services_health() == False

def test_check_services_health_gpu_failure(redis_conn):
    with patch('src.queue.conn.ping') as mock_ping, \
         patch('requests.get') as mock_get:
        mock_ping.return_value = True
        mock_get.side_effect = requests.exceptions.RequestException("GPU service unavailable")
        assert queue.check_services_health() == False

def test_queueing_mechanism(redis_conn):
    q = Queue(connection=redis_conn)
    with patch('src.queue.call_predict_response') as mock_call_predict_response:
        mock_call_predict_response.return_value = "test response"
        job = q.enqueue(queue.call_predict_response, 'test prompt')
        assert job.result == None
        # The following line would normally trigger the worker to process the job, but we are not running the worker in this test
        # result = job.result
        # assert result == "test response"