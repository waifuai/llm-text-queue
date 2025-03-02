import os
import redis
import logging
from rq import Worker, Queue, Connection

listen = ['default']

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    with Connection(conn):
        worker = Worker(list(map(Queue, listen)))
        try:
            worker.work()
        except Exception as e:
            logging.exception("Worker failed to start")
