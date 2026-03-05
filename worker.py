import os

import redis
from rq import Worker, Queue

listen = ["high", "default", "low"]

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

conn = redis.from_url(redis_url)

if __name__ == "__main__":
    queues = [Queue(name, connection=conn) for name in listen]
    worker = Worker(queues, connection=conn)
    worker.work()
