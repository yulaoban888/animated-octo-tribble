from fastapi import Request
import time
from prometheus_client import Counter, Histogram
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

async def performance_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    # 计算请求处理时间
    process_time = time.time() - start_time
    
    # 记录metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(process_time)
    
    # 记录慢请求
    if process_time > 1.0:  # 超过1秒的请求
        logger.warning(
            f"Slow request: {request.method} {request.url.path} "
            f"took {process_time:.2f} seconds"
        )
    
    return response 