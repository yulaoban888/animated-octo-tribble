import os
import subprocess
import boto3
import logging
from datetime import datetime
from typing import Optional, List, Dict
import json
import time

logger = logging.getLogger(__name__)

class DisasterRecovery:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.backup_bucket = os.getenv("BACKUP_BUCKET", "warehouse-backups")
        self.recovery_dir = "/app/recovery"
        os.makedirs(self.recovery_dir, exist_ok=True)
    
    def list_backups(self) -> List[Dict]:
        """列出所有可用的备份"""
        try:
            response = self.s3.list_objects_v2(Bucket=self.backup_bucket)
            backups = []
            
            for obj in response.get('Contents', []):
                backup_info = {
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat(),
                    "type": obj['Key'].split('/')[-1].split('_')[0]
                }
                backups.append(backup_info)
            
            return sorted(backups, key=lambda x: x['last_modified'], reverse=True)
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def download_backup(self, backup_key: str) -> Optional[str]:
        """下载备份文件"""
        try:
            local_path = os.path.join(self.recovery_dir, backup_key.split('/')[-1])
            self.s3.download_file(self.backup_bucket, backup_key, local_path)
            return local_path
        except Exception as e:
            logger.error(f"Failed to download backup: {e}")
            return None
    
    def restore_database(self, backup_file: str) -> bool:
        """恢复数据库"""
        try:
            # 停止应用服务
            subprocess.run(["docker-compose", "stop", "api"], check=True)
            
            # 删除现有数据库
            subprocess.run([
                "dropdb",
                "-h", "localhost",
                "-U", "user",
                "warehouse_db"
            ], check=True)
            
            # 创建新数据库
            subprocess.run([
                "createdb",
                "-h", "localhost",
                "-U", "user",
                "warehouse_db"
            ], check=True)
            
            # 恢复数据
            subprocess.run([
                "pg_restore",
                "-h", "localhost",
                "-U", "user",
                "-d", "warehouse_db",
                backup_file
            ], check=True)
            
            # 启动应用服务
            subprocess.run(["docker-compose", "start", "api"], check=True)
            
            return True
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
    
    def verify_recovery(self) -> bool:
        """验证恢复结果"""
        try:
            # 检查数据库连接
            subprocess.run([
                "psql",
                "-h", "localhost",
                "-U", "user",
                "-d", "warehouse_db",
                "-c", "SELECT 1"
            ], check=True)
            
            # 检查API服务
            response = requests.get("http://localhost:8000/health")
            if response.status_code != 200:
                raise Exception("API health check failed")
            
            return True
        except Exception as e:
            logger.error(f"Recovery verification failed: {e}")
            return False
    
    def perform_recovery(self, backup_key: Optional[str] = None) -> bool:
        """执行灾难恢复"""
        try:
            # 如果未指定备份，使用最新的
            if not backup_key:
                backups = self.list_backups()
                if not backups:
                    raise Exception("No backups available")
                backup_key = backups[0]['key']
            
            # 下载备份
            backup_file = self.download_backup(backup_key)
            if not backup_file:
                raise Exception("Failed to download backup")
            
            # 恢复数据库
            if not self.restore_database(backup_file):
                raise Exception("Failed to restore database")
            
            # 验证恢复
            if not self.verify_recovery():
                raise Exception("Recovery verification failed")
            
            logger.info(f"Recovery completed successfully using backup: {backup_key}")
            return True
            
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            return False
        finally:
            # 清理临时文件
            if os.path.exists(self.recovery_dir):
                shutil.rmtree(self.recovery_dir)

if __name__ == "__main__":
    recovery = DisasterRecovery()
    recovery.perform_recovery() 