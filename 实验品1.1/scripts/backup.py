import os
import time
from datetime import datetime
import boto3
import subprocess
from pathlib import Path

# AWS S3配置
S3_BUCKET = os.getenv('S3_BUCKET', 'warehouse-backups')
AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-1')

# 本地备份目录
BACKUP_DIR = Path("/app/backups")
BACKUP_DIR.mkdir(exist_ok=True)

def create_db_backup():
    """创建数据库备份"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f"db_backup_{timestamp}.sql"
    
    try:
        # 执行pg_dump
        subprocess.run([
            'pg_dump',
            '-h', os.getenv('DB_HOST', 'db'),
            '-U', os.getenv('DB_USER', 'user'),
            '-d', os.getenv('DB_NAME', 'warehouse_db'),
            '-f', str(backup_file)
        ], check=True)
        
        return backup_file
    except Exception as e:
        print(f"Backup failed: {e}")
        return None

def upload_to_s3(file_path: Path):
    """上传备份到S3"""
    s3 = boto3.client('s3', region_name=AWS_REGION)
    try:
        s3.upload_file(
            str(file_path),
            S3_BUCKET,
            f"backups/{file_path.name}"
        )
        return True
    except Exception as e:
        print(f"Upload to S3 failed: {e}")
        return False

def cleanup_old_backups():
    """清理旧的备份文件"""
    # 保留最近7天的备份
    retention_days = 7
    current_time = time.time()
    
    for backup_file in BACKUP_DIR.glob("db_backup_*.sql"):
        if (current_time - backup_file.stat().st_mtime) > (retention_days * 86400):
            backup_file.unlink()

if __name__ == "__main__":
    backup_file = create_db_backup()
    if backup_file:
        if upload_to_s3(backup_file):
            print(f"Backup {backup_file.name} uploaded to S3")
        cleanup_old_backups() 