from functools import wraps
from datetime import datetime, timedelta
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache(expire_seconds=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # 尝试从缓存获取
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
            
            # 执行原函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            redis_client.setex(
                cache_key,
                expire_seconds,
                json.dumps(result)
            )
            
            return result
        return wrapper
    return decorator 