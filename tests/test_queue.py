import pytest
from unittest.mock import patch
from src import api_queue as queue # Renamed import
# from src import config # No longer needed for REDIS_URL
import redis
import fakeredis # Import fakeredis
from rq import Queue

@pytest.fixture
def redis_conn():
    # Use fakeredis for testing instead of a real Redis connection
    return fakeredis.FakeStrictRedis()

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
        mock_post.side_effect = Exception('test error') # Changed to a generic Exception
        response = queue.call_predict_response('test prompt')
    assert response == "Error: Could not connect to the GPU service." # This error message might need updating depending on the actual error handling in api_queue.py

def test_test_worker():
    assert queue.test_worker() == "test worker"

def test_check_services_health_success(redis_conn):
    with patch('src.api_queue.conn.ping') as mock_ping, \
         patch('rq.Queue.enqueue_call') as mock_enqueue_call: # Removed requests.get patch
        mock_ping.return_value = True
        mock_enqueue_call.return_value.get_status.return_value = "queued"
        assert queue.check_services_health() == True

def test_check_services_health_redis_failure(redis_conn):
    with patch('src.api_queue.conn.ping', side_effect=redis.exceptions.ConnectionError("Redis unavailable")):
        assert queue.check_services_health() == False

def test_queueing_mechanism(redis_conn):
    q = Queue(connection=redis_conn)
    # Test enqueueing a simple, pickleable function to verify connection
    # No need to patch call_predict_response here as we are not calling it
    # We use test_worker which is defined in api_queue and known to be simple
    job = q.enqueue(queue.test_worker) # Enqueue a simple function
    assert job.id is not None # Check that the job was created successfully
    # The following line would normally trigger the worker to process the job, but we are not running the worker in this test
    # result = job.result
    # assert result == "test response"