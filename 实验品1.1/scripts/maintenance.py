import psutil
import shutil
import os
import subprocess
from datetime import datetime
import logging
import requests
from typing import Dict, List
import json

logger = logging.getLogger(__name__)

class SystemMaintenance:
    def __init__(self):
        self.thresholds = {
            "disk_usage": 85,  # 磁盘使用率警告阈值
            "memory_usage": 90,  # 内存使用率警告阈值
            "cpu_usage": 80,    # CPU使用率警告阈值
            "log_days": 30,     # 日志保留天数
            "backup_days": 7    # 备份保留天数
        }
    
    def check_system_health(self) -> Dict:
        """检查系统健康状态"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # 进程数量
            process_count = len(psutil.pids())
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory_percent,
                "disk_usage": disk_percent,
                "process_count": process_count,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {}
    
    def cleanup_old_logs(self, log_dir: str):
        """清理旧日志文件"""
        try:
            current_time = datetime.now()
            for file in os.listdir(log_dir):
                file_path = os.path.join(log_dir, file)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if (current_time - file_time).days > self.thresholds["log_days"]:
                        os.remove(file_path)
                        logger.info(f"Removed old log file: {file}")
        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")
    
    def cleanup_old_backups(self, backup_dir: str):
        """清理旧备份文件"""
        try:
            current_time = datetime.now()
            for file in os.listdir(backup_dir):
                file_path = os.path.join(backup_dir, file)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if (current_time - file_time).days > self.thresholds["backup_days"]:
                        os.remove(file_path)
                        logger.info(f"Removed old backup file: {file}")
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    def check_services(self) -> Dict[str, str]:
        """检查服务状态"""
        services = {
            "api": "http://localhost:8000/health",
            "db": "postgresql://user:password@localhost:5432",
            "redis": "redis://localhost:6379",
            "elasticsearch": "http://localhost:9200"
        }
        
        status = {}
        for service, url in services.items():
            try:
                if service == "api":
                    response = requests.get(url)
                    status[service] = "healthy" if response.status_code == 200 else "unhealthy"
                else:
                    # 这里可以添加其他服务的健康检查逻辑
                    status[service] = "unknown"
            except Exception as e:
                status[service] = "unhealthy"
                logger.error(f"Service check failed for {service}: {e}")
        
        return status

    def perform_maintenance(self):
        """执行维护任务"""
        try:
            # 检查系统健康状态
            health = self.check_system_health()
            
            # 检查服务状态
            services = self.check_services()
            
            # 清理日志和备份
            self.cleanup_old_logs("/var/log/warehouse")
            self.cleanup_old_backups("/app/backups")
            
            # 记录维护结果
            maintenance_record = {
                "timestamp": datetime.now().isoformat(),
                "health": health,
                "services": services
            }
            
            with open("/var/log/warehouse/maintenance.log", "a") as f:
                json.dump(maintenance_record, f)
                f.write("\n")
            
            return maintenance_record
        except Exception as e:
            logger.error(f"Maintenance failed: {e}")
            return None

if __name__ == "__main__":
    maintenance = SystemMaintenance()
    maintenance.perform_maintenance() 