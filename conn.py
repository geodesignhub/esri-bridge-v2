from os import environ as env
from redis import Redis, ConnectionPool, SSLConnection, Connection

def get_redis():
    redis_url = env.get("REDIS_URL", "redis://localhost:6379")

    # Determine if SSL is required
    is_ssl = redis_url.startswith("rediss://")

    # Use SSLConnection for SSL, otherwise use default Connection class
    connection_class = SSLConnection if is_ssl else Connection

    # Create the connection pool explicitly
    connection_pool = ConnectionPool.from_url(
        redis_url,
        connection_class=connection_class  # Explicitly pass the connection class
    )

    # Return Redis client using the connection pool
    return Redis(connection_pool=connection_pool)
