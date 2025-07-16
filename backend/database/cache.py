from cachetools import TTLCache

local_cache = TTLCache(maxsize=600, ttl=600)
