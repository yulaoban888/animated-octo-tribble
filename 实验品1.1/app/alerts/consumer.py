import json
import logging
from ..queue.rabbitmq import RabbitMQ
from .handlers import AlertHandler

logger = logging.getLogger(__name__)

class AlertConsumer:
    def __init__(self):
        self.rabbitmq = RabbitMQ()
        self.alert_handler = AlertHandler()
    
    def process_stock_alert(self, ch, method, properties, body):
        """处理库存相关告警"""
        try:
            alert_data = json.loads(body)
            alert_type = alert_data.get("type")
            
            if alert_type == "low_stock":
                self.alert_handler.send_email_alert(
                    subject="Low Stock Alert",
                    message=f"Product {alert_data['product_id']} is running low: {alert_data['quantity']} units remaining",
                    recipients=["warehouse@example.com"]
                )
            
            elif alert_type == "expiry_warning":
                self.alert_handler.send_email_alert(
                    subject="Product Expiry Warning",
                    message=f"Product {alert_data['product_id']} will expire in {alert_data['days_remaining']} days",
                    recipients=["warehouse@example.com"]
                )
            
        except Exception as e:
            logger.error(f"Failed to process stock alert: {e}")
    
    def process_system_alert(self, ch, method, properties, body):
        """处理系统相关告警"""
        try:
            alert_data = json.loads(body)
            alert_type = alert_data.get("type")
            
            if alert_type == "high_error_rate":
                self.alert_handler.send_webhook_alert({
                    "title": "High Error Rate Detected",
                    "description": f"Error rate: {alert_data['value']:.2%}",
                    "severity": "high"
                })
            
            elif alert_type == "slow_response":
                self.alert_handler.send_webhook_alert({
                    "title": "Slow Response Time Detected",
                    "description": f"Response time: {alert_data['value']:.2f}s",
                    "severity": "medium"
                })
            
        except Exception as e:
            logger.error(f"Failed to process system alert: {e}")
    
    def start(self):
        """启动告警消费者"""
        try:
            # 启动库存告警消费者
            self.rabbitmq.consume("stock_alerts", self.process_stock_alert)
            
            # 启动系统告警消费者
            self.rabbitmq.consume("system_events", self.process_system_alert)
            
        except Exception as e:
            logger.error(f"Failed to start alert consumer: {e}") 