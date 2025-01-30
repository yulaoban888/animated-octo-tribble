from functools import wraps
import hashlib
import json
from typing import Any, Optional
import redis
from datetime import datetime, timedelta

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = 300  # 5分钟
    
    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [prefix]
        if args:
            key_parts.extend([str(arg) for arg in args])
        if kwargs:
            key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
        
        key = ":".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        data = json.dumps(value)
        self.redis.setex(key, ttl or self.default_ttl, data)
    
    def delete(self, key: str):
        """删除缓存"""
        self.redis.delete(key)
    
    def clear_pattern(self, pattern: str):
        """清除匹配模式的缓存"""
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

# 创建缓存装饰器
def cache(prefix: str, ttl: Optional[int] = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = cache_manager.generate_key(prefix, *args, **kwargs)
            cached_data = cache_manager.get(cache_key)
            
            if cached_data is not None:
                return cached_data
            
            result = await func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

# 创建缓存管理器实例
cache_manager = CacheManager("redis://redis:6379/0") 