from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time
from typing import Dict, List
import psutil

# 请求指标
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# 业务指标
STOCK_LEVEL = Gauge(
    "warehouse_stock_level",
    "Current stock level",
    ["product_id", "warehouse_id"]
)

INBOUND_COUNT = Counter(
    "warehouse_inbound_total",
    "Total inbound records",
    ["product_id", "warehouse_id"]
)

OUTBOUND_COUNT = Counter(
    "warehouse_outbound_total",
    "Total outbound records",
    ["product_id", "warehouse_id"]
)

# 系统指标
SYSTEM_MEMORY = Gauge(
    "system_memory_usage_bytes",
    "System memory usage in bytes",
    ["type"]
)

SYSTEM_CPU = Gauge(
    "system_cpu_usage_percent",
    "System CPU usage percentage",
    ["cpu"]
)

def collect_system_metrics():
    """收集系统指标"""
    # 内存使用
    memory = psutil.virtual_memory()
    SYSTEM_MEMORY.labels("total").set(memory.total)
    SYSTEM_MEMORY.labels("used").set(memory.used)
    SYSTEM_MEMORY.labels("free").set(memory.free)
    
    # CPU使用
    for i, percentage in enumerate(psutil.cpu_percent(percpu=True)):
        SYSTEM_CPU.labels(f"cpu{i}").set(percentage)

def monitor_request():
    """请求监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            method = kwargs.get("request").method
            endpoint = kwargs.get("request").url.path
            
            start_time = time.time()
            try:
                response = await func(*args, **kwargs)
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    status=response.status_code
                ).inc()
                return response
            finally:
                REQUEST_LATENCY.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(time.time() - start_time)
        return wrapper
    return decorator

def update_stock_metrics(product_id: int, warehouse_id: int, quantity: int):
    """更新库存指标"""
    STOCK_LEVEL.labels(
        product_id=str(product_id),
        warehouse_id=str(warehouse_id)
    ).set(quantity)

def record_inbound(product_id: int, warehouse_id: int):
    """记录入库指标"""
    INBOUND_COUNT.labels(
        product_id=str(product_id),
        warehouse_id=str(warehouse_id)
    ).inc()

def record_outbound(product_id: int, warehouse_id: int):
    """记录出库指标"""
    OUTBOUND_COUNT.labels(
        product_id=str(product_id),
        warehouse_id=str(warehouse_id)
    ).inc() 