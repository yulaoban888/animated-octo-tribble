import logging
from elasticsearch import Elasticsearch
from datetime import datetime
import json
from typing import Dict, Any
import os

class LogCollector:
    def __init__(self):
        self.es = Elasticsearch([os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")])
        self.index_prefix = "warehouse-logs-"
    
    def get_index_name(self) -> str:
        """获取当前日期的索引名"""
        return f"{self.index_prefix}{datetime.now().strftime('%Y.%m.%d')}"
    
    def format_log(self, record: logging.LogRecord) -> Dict[str, Any]:
        """格式化日志记录"""
        return {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "path": record.pathname,
            "line_number": record.lineno,
            "function": record.funcName,
            "exception": record.exc_info[1] if record.exc_info else None,
            "trace_id": getattr(record, "trace_id", None),
            "service": os.getenv("SERVICE_NAME", "warehouse-api")
        }
    
    def send_to_elasticsearch(self, log_data: Dict[str, Any]):
        """发送日志到Elasticsearch"""
        try:
            self.es.index(
                index=self.get_index_name(),
                document=log_data
            )
        except Exception as e:
            print(f"Failed to send log to Elasticsearch: {e}")

class ElasticsearchHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.collector = LogCollector()
    
    def emit(self, record):
        try:
            log_data = self.collector.format_log(record)
            self.collector.send_to_elasticsearch(log_data)
        except Exception as e:
            print(f"Failed to emit log: {e}") 