from fastapi import Request, HTTPException
from typing import Optional
import time
from datetime import datetime, timedelta
import ipaddress
from .config import security_config
import redis
from collections import defaultdict

# Redis连接
redis_client = redis.from_url("redis://redis:6379/1")

# 内存存储
request_counts = defaultdict(list)
failed_login_attempts = defaultdict(int)
blocked_ips = {}

async def security_middleware(request: Request, call_next):
    client_ip = request.client.host
    
    # IP检查
    if security_config.IP_BLACKLIST and client_ip in security_config.IP_BLACKLIST:
        raise HTTPException(status_code=403, detail="IP blocked")
    
    if security_config.IP_WHITELIST and client_ip not in security_config.IP_WHITELIST:
        raise HTTPException(status_code=403, detail="IP not allowed")
    
    # 速率限制
    if security_config.RATE_LIMIT_ENABLED:
        key = f"rate_limit:{client_ip}"
        current = int(redis_client.get(key) or 0)
        
        if current >= security_config.RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Too many requests")
        
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)
        pipe.execute()
    
    # 处理请求
    response = await call_next(request)
    
    # 添加安全头部
    for header, value in security_config.SECURITY_HEADERS.items():
        response.headers[header] = value
    
    return response

def record_failed_login(username: str, ip: str):
    """记录登录失败"""
    key = f"failed_login:{username}"
    current = int(redis_client.get(key) or 0)
    
    if current >= security_config.MAX_FAILED_LOGIN_ATTEMPTS:
        block_ip(ip)
    else:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, security_config.ACCOUNT_LOCKOUT_MINUTES * 60)
        pipe.execute()

def reset_failed_login(username: str):
    """重置登录失败计数"""
    redis_client.delete(f"failed_login:{username}")

def block_ip(ip: str):
    """封禁IP"""
    redis_client.setex(
        f"blocked_ip:{ip}",
        security_config.ACCOUNT_LOCKOUT_MINUTES * 60,
        1
    )

def is_ip_blocked(ip: str) -> bool:
    """检查IP是否被封禁"""
    return bool(redis_client.get(f"blocked_ip:{ip}")) 