import hashlib
import json
import time
from .config import settings
class MemoryCache:
    """Fallback cache that lives inside the python process."""
    def __init__(self):
        self.data = {}
    def get(self, key):
        item = self.data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at < time.time():
            del self.data[key]
            return None
        return value
    def set(self, key, value, ttl):
        self.data[key] = (value, time.time() + ttl)
class RedisCache:
    def __init__(self, url):
        import redis
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.client.ping()  # fail early if redis is not reachable
    def get(self, key):
        raw = self.client.get(key)
        return json.loads(raw) if raw else None
    def set(self, key, value, ttl):
        self.client.set(key, json.dumps(value), ex=ttl)
class Cache:
    def __init__(self):
        self.backend = self.make_backend()
        self.hits = 0
        self.misses = 0
    def make_backend(self):
        if settings.redis_url:
            try:
                return RedisCache(settings.redis_url)
            except Exception as e:
                print("redis not available, using memory cache:", e)
        return MemoryCache()
    def get(self, key):
        value = self.backend.get(key)
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value
    def set(self, key, value, ttl):
        self.backend.set(key, value, ttl)
    def info(self):
        total = self.hits + self.misses
        return {
            "backend": type(self.backend).__name__,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 2) if total else 0,
        }
cache = Cache()
def make_key(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
def index_version():
    return cache.backend.get("index_version") or 0
def bump_index_version():
    cache.backend.set("index_version", index_version() + 1, 60 * 60 * 24 * 365)