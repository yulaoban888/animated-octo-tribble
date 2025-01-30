import pika
import json
from typing import Callable, Any
import logging
from functools import wraps

logger = logging.getLogger(__name__)

class RabbitMQ:
    def __init__(self, host: str = "rabbitmq", port: int = 5672):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port)
        )
        self.channel = self.connection.channel()
        
        # 声明队列
        self.channel.queue_declare(queue='stock_alerts')
        self.channel.queue_declare(queue='system_events')
        self.channel.queue_declare(queue='audit_logs')
    
    def publish(self, queue: str, message: dict):
        """发布消息到指定队列"""
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps(message)
            )
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
    
    def consume(self, queue: str, callback: Callable):
        """从指定队列消费消息"""
        self.channel.basic_consume(
            queue=queue,
            on_message_callback=callback,
            auto_ack=True
        )
        self.channel.start_consuming()

def async_task(queue: str):
    """异步任务装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rabbitmq = RabbitMQ()
            task_data = {
                "function": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            rabbitmq.publish(queue, task_data)
        return wrapper
    return decorator 