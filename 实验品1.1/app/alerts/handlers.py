from typing import List, Dict
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import requests
import logging
from ..queue.rabbitmq import RabbitMQ

logger = logging.getLogger(__name__)

class AlertHandler:
    def __init__(self):
        self.rabbitmq = RabbitMQ()
        self.alert_thresholds = {
            "low_stock": 10,
            "expiry_days": 30,
            "error_rate": 0.05,
            "response_time": 1.0
        }
    
    def send_email_alert(self, subject: str, message: str, recipients: List[str]):
        """发送邮件告警"""
        try:
            msg = MIMEText(message)
            msg['Subject'] = subject
            msg['From'] = "alerts@warehouse.com"
            msg['To'] = ", ".join(recipients)
            
            with smtplib.SMTP('smtp.warehouse.com') as server:
                server.send_message(msg)
                
            logger.info(f"Alert email sent to {recipients}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def send_webhook_alert(self, alert_data: Dict):
        """发送Webhook告警"""
        try:
            response = requests.post(
                "https://webhook.warehouse.com/alerts",
                json=alert_data
            )
            response.raise_for_status()
            logger.info("Webhook alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def handle_stock_alert(self, product_id: int, quantity: int):
        """处理库存告警"""
        if quantity <= self.alert_thresholds["low_stock"]:
            alert_data = {
                "type": "low_stock",
                "product_id": product_id,
                "quantity": quantity,
                "timestamp": datetime.now().isoformat()
            }
            self.rabbitmq.publish("stock_alerts", alert_data)
    
    def handle_expiry_alert(self, product_id: int, expiry_date: datetime):
        """处理过期告警"""
        days_until_expiry = (expiry_date - datetime.now()).days
        if days_until_expiry <= self.alert_thresholds["expiry_days"]:
            alert_data = {
                "type": "expiry_warning",
                "product_id": product_id,
                "expiry_date": expiry_date.isoformat(),
                "days_remaining": days_until_expiry,
                "timestamp": datetime.now().isoformat()
            }
            self.rabbitmq.publish("stock_alerts", alert_data)
    
    def handle_system_alert(self, metric: str, value: float):
        """处理系统告警"""
        if metric == "error_rate" and value > self.alert_thresholds["error_rate"]:
            alert_data = {
                "type": "high_error_rate",
                "value": value,
                "threshold": self.alert_thresholds["error_rate"],
                "timestamp": datetime.now().isoformat()
            }
            self.rabbitmq.publish("system_events", alert_data)
        
        elif metric == "response_time" and value > self.alert_thresholds["response_time"]:
            alert_data = {
                "type": "slow_response",
                "value": value,
                "threshold": self.alert_thresholds["response_time"],
                "timestamp": datetime.now().isoformat()
            }
            self.rabbitmq.publish("system_events", alert_data) 