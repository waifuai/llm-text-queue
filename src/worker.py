import os
import redis
import logging
from rq import Worker, Queue

listen = ['default']

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # The Connection context is managed by the Worker itself
    worker = Worker(list(map(Queue, listen)), connection=conn)
    try:
        worker.work()
    except Exception as e:
        logging.exception("Worker failed to start")
