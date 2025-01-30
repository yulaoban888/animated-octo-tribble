from fastapi import Request, HTTPException
from typing import Dict, List
from datetime import datetime, timedelta
import time
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)

# 请求限制计数器
request_counts: Dict[str, List[float]] = defaultdict(list)
failed_login_attempts: Dict[str, int] = defaultdict(int)
blocked_ips: Dict[str, datetime] = {}

async def security_middleware(request: Request, call_next):
    # 获取客户端IP
    client_ip = request.client.host
    
    # 检查IP是否被封禁
    if client_ip in blocked_ips:
        if datetime.now() < blocked_ips[client_ip]:
            raise HTTPException(status_code=403, detail="IP temporarily blocked")
        else:
            del blocked_ips[client_ip]
    
    # 速率限制
    current_time = time.time()
    request_counts[client_ip] = [t for t in request_counts[client_ip] 
                               if current_time - t < 60]
    request_counts[client_ip].append(current_time)
    
    if len(request_counts[client_ip]) > 60:
        raise HTTPException(status_code=429, detail="Too many requests")
    
    # 安全头部
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

def validate_password(password: str) -> bool:
    """验证密码强度"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def record_failed_login(username: str, ip: str):
    """记录登录失败"""
    failed_login_attempts[username] += 1
    if failed_login_attempts[username] >= 5:
        blocked_ips[ip] = datetime.now() + timedelta(minutes=15)
        logger.warning(f"IP {ip} blocked due to multiple failed login attempts")

def reset_failed_login(username: str):
    """重置登录失败计数"""
    if username in failed_login_attempts:
        del failed_login_attempts[username] 