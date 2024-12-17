import os
from urllib.parse import urlparse
import redis
def get_redis():

    url = urlparse(os.environ.get("REDIS_URL"))
    r = redis.Redis(host=url.hostname, port=url.port, password=url.password, ssl=(url.scheme == "rediss"), ssl_cert_reqs=None)
    return r 