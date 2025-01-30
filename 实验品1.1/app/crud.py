from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.sql import func
from . import security
from typing import Optional
import csv
import os
import json
from statistics import mean
from collections import defaultdict
import shutil
import subprocess
from pathlib import Path
from .cache import cache

BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not security.verify_password(password, user.hashed_password):
        return False
    return user

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        role=user.role,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@cache(expire_seconds=300)
def get_products(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Product).offset(skip).limit(limit).all()

def create_product(db: Session, product: schemas.ProductCreate):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def create_inbound_record(db: Session, inbound: schemas.InboundRecordCreate, operator_id: int):
    # 创建入库记录
    db_inbound = models.InboundRecord(**inbound.dict(), operator_id=operator_id)
    db.add(db_inbound)
    
    # 更新库存
    stock = db.query(models.Stock).filter(
        models.Stock.product_id == inbound.product_id,
        models.Stock.warehouse_id == inbound.warehouse_id
    ).first()
    
    if stock:
        stock.quantity += inbound.quantity
    else:
        stock = models.Stock(
            product_id=inbound.product_id,
            warehouse_id=inbound.warehouse_id,
            quantity=inbound.quantity,
            expiry_date=inbound.expiry_date
        )
        db.add(stock)
    
    # 记录操作日志
    log = models.OperationLog(
        operation_type="inbound",
        operation_detail=f"Product {inbound.product_id} inbound, quantity: {inbound.quantity}",
        operator_id=operator_id
    )
    db.add(log)
    
    db.commit()
    db.refresh(db_inbound)
    return db_inbound

def create_outbound_record(db: Session, outbound: schemas.OutboundRecordCreate):
    # 检查库存是否充足
    stock = db.query(models.Stock).filter(
        models.Stock.product_id == outbound.product_id,
        models.Stock.warehouse_id == outbound.warehouse_id
    ).first()
    
    if not stock or stock.quantity < outbound.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    
    # 创建出库记录
    db_outbound = models.OutboundRecord(**outbound.dict())
    db.add(db_outbound)
    
    # 更新库存
    stock.quantity -= outbound.quantity
    
    db.commit()
    db.refresh(db_outbound)
    return db_outbound

@cache(expire_seconds=60)
def get_product_stock(db: Session, product_id: int):
    return db.query(models.Stock).filter(models.Stock.product_id == product_id).all()

def get_stock_warnings(db: Session):
    """获取库存预警信息"""
    warnings = []
    stocks = db.query(models.Stock).join(models.Product).all()
    
    for stock in stocks:
        if stock.quantity <= stock.product.min_stock:
            warnings.append({
                "product": stock.product,
                "current_quantity": stock.quantity,
                "min_stock": stock.product.min_stock,
                "warehouse": stock.warehouse.name
            })
    return warnings

def get_expiry_warnings(db: Session, days_threshold: int = 30):
    """获取保质期预警信息"""
    warnings = []
    warning_date = datetime.utcnow() + timedelta(days=days_threshold)
    
    stocks = db.query(models.Stock).filter(
        models.Stock.expiry_date <= warning_date
    ).all()
    
    for stock in stocks:
        days_until_expiry = (stock.expiry_date - datetime.utcnow()).days
        warnings.append({
            "product": stock.product,
            "quantity": stock.quantity,
            "expiry_date": stock.expiry_date,
            "days_until_expiry": days_until_expiry,
            "warehouse": stock.warehouse.name
        })
    return warnings

def create_stock_transfer(db: Session, transfer: schemas.StockTransferCreate):
    """创建库存调拨记录"""
    # 检查源仓库库存
    from_stock = db.query(models.Stock).filter(
        models.Stock.product_id == transfer.product_id,
        models.Stock.warehouse_id == transfer.from_warehouse_id
    ).first()
    
    if not from_stock or from_stock.quantity < transfer.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock in source warehouse")
    
    # 更新源仓库库存
    from_stock.quantity -= transfer.quantity
    
    # 更新目标仓库库存
    to_stock = db.query(models.Stock).filter(
        models.Stock.product_id == transfer.product_id,
        models.Stock.warehouse_id == transfer.to_warehouse_id
    ).first()
    
    if to_stock:
        to_stock.quantity += transfer.quantity
    else:
        to_stock = models.Stock(
            product_id=transfer.product_id,
            warehouse_id=transfer.to_warehouse_id,
            quantity=transfer.quantity,
            expiry_date=from_stock.expiry_date
        )
        db.add(to_stock)
    
    # 创建调拨记录
    db_transfer = models.StockTransfer(**transfer.dict())
    db.add(db_transfer)
    
    db.commit()
    return db_transfer

def get_stock_statistics(db: Session, start_date: datetime, end_date: datetime):
    """获取库存统计数据"""
    inbound_stats = db.query(
        models.InboundRecord.product_id,
        func.sum(models.InboundRecord.quantity).label('total_in')
    ).filter(
        models.InboundRecord.created_at.between(start_date, end_date)
    ).group_by(models.InboundRecord.product_id).all()
    
    outbound_stats = db.query(
        models.OutboundRecord.product_id,
        func.sum(models.OutboundRecord.quantity).label('total_out')
    ).filter(
        models.OutboundRecord.created_at.between(start_date, end_date)
    ).group_by(models.OutboundRecord.product_id).all()
    
    return {
        "inbound": inbound_stats,
        "outbound": outbound_stats
    }

def get_operation_logs(
    db: Session, 
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    operation_type: Optional[str] = None
):
    query = db.query(models.OperationLog)
    
    if start_date:
        query = query.filter(models.OperationLog.created_at >= start_date)
    if end_date:
        query = query.filter(models.OperationLog.created_at <= end_date)
    if operation_type:
        query = query.filter(models.OperationLog.operation_type == operation_type)
        
    return query.order_by(models.OperationLog.created_at.desc()).all()

def process_barcode(db: Session, barcode_info: schemas.BarcodeInfo):
    """处理条码扫描"""
    # 查找现有产品
    product = db.query(models.Product).filter(
        models.Product.barcode == barcode_info.barcode
    ).first()
    
    if product:
        return {
            "exists": True,
            "product": product
        }
    
    # 如果提供了产品信息，创建新产品
    if barcode_info.name:
        new_product = models.Product(
            barcode=barcode_info.barcode,
            name=barcode_info.name,
            category=barcode_info.category,
            unit=barcode_info.unit,
            price=barcode_info.price
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        return {
            "exists": False,
            "product": new_product
        }
    
    return {
        "exists": False,
        "product": None
    }

def export_stock_data(db: Session, warehouse_id: Optional[int], category: Optional[str]) -> str:
    """导出库存数据到CSV文件"""
    query = db.query(
        models.Stock,
        models.Product,
        models.Warehouse
    ).join(
        models.Product
    ).join(
        models.Warehouse
    )
    
    if warehouse_id:
        query = query.filter(models.Stock.warehouse_id == warehouse_id)
    if category:
        query = query.filter(models.Product.category == category)
    
    results = query.all()
    
    # 创建CSV文件
    file_path = f"temp/stock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    os.makedirs("temp", exist_ok=True)
    
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Product ID', 'Product Name', 'Category', 'Warehouse',
            'Quantity', 'Shelf Number', 'Expiry Date'
        ])
        
        for stock, product, warehouse in results:
            writer.writerow([
                product.id,
                product.name,
                product.category,
                warehouse.name,
                stock.quantity,
                stock.shelf_number,
                stock.expiry_date.strftime('%Y-%m-%d')
            ])
    
    return file_path

def export_transactions(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    transaction_type: Optional[str]
) -> str:
    """导出交易记录到CSV文件"""
    inbound_query = db.query(
        models.InboundRecord,
        models.Product,
        models.Warehouse,
        models.Supplier
    ).join(
        models.Product
    ).join(
        models.Warehouse
    ).join(
        models.Supplier
    ).filter(
        models.InboundRecord.created_at.between(start_date, end_date)
    )
    
    outbound_query = db.query(
        models.OutboundRecord,
        models.Product,
        models.Warehouse
    ).join(
        models.Product
    ).join(
        models.Warehouse
    ).filter(
        models.OutboundRecord.created_at.between(start_date, end_date)
    )
    
    file_path = f"temp/transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    os.makedirs("temp", exist_ok=True)
    
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Transaction Type', 'Date', 'Product', 'Warehouse',
            'Quantity', 'Reference', 'Details'
        ])
        
        if transaction_type != 'outbound':
            for inbound, product, warehouse, supplier in inbound_query:
                writer.writerow([
                    'Inbound',
                    inbound.created_at.strftime('%Y-%m-%d %H:%M'),
                    product.name,
                    warehouse.name,
                    inbound.quantity,
                    inbound.batch_number,
                    f"Supplier: {supplier.name}"
                ])
        
        if transaction_type != 'inbound':
            for outbound, product, warehouse in outbound_query:
                writer.writerow([
                    'Outbound',
                    outbound.created_at.strftime('%Y-%m-%d %H:%M'),
                    product.name,
                    warehouse.name,
                    outbound.quantity,
                    outbound.order_id,
                    outbound.reason
                ])
    
    return file_path

def queue_offline_operation(db: Session, operation_type: str, data: dict):
    """将离线操作加入同步队列"""
    sync_item = models.SyncQueue(
        operation_type=operation_type,
        data=json.dumps(data)
    )
    db.add(sync_item)
    db.commit()
    db.refresh(sync_item)
    return sync_item

def process_sync_queue(db: Session):
    """处理同步队列"""
    pending_items = db.query(models.SyncQueue).filter(
        models.SyncQueue.status == "pending",
        models.SyncQueue.retry_count < 3
    ).all()
    
    for item in pending_items:
        try:
            data = json.loads(item.data)
            if item.operation_type == "inbound":
                create_inbound_record(db, schemas.InboundRecordCreate(**data))
            elif item.operation_type == "outbound":
                create_outbound_record(db, schemas.OutboundRecordCreate(**data))
            
            item.status = "synced"
        except Exception as e:
            item.status = "failed"
            item.retry_count += 1
        
        item.last_attempt = datetime.utcnow()
        db.commit()

def get_inventory_analysis(db: Session, days: int = 90):
    """获取库存分析数据"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # 获取当前库存
    current_stocks = db.query(
        models.Stock.product_id,
        models.Product.name,
        func.sum(models.Stock.quantity).label('current_stock')
    ).join(models.Product).group_by(models.Stock.product_id, models.Product.name).all()
    
    # 获取消耗数据
    outbound_data = db.query(
        models.OutboundRecord.product_id,
        func.sum(models.OutboundRecord.quantity).label('total_out'),
        func.count(models.OutboundRecord.id).label('transaction_count')
    ).filter(
        models.OutboundRecord.created_at.between(start_date, end_date)
    ).group_by(models.OutboundRecord.product_id).all()
    
    analysis_results = []
    for stock in current_stocks:
        outbound = next((o for o in outbound_data if o.product_id == stock.product_id), None)
        if outbound:
            monthly_consumption = (outbound.total_out * 30) / days
            turnover_rate = outbound.total_out / stock.current_stock if stock.current_stock > 0 else 0
            
            analysis_results.append({
                "product_id": stock.product_id,
                "product_name": stock.name,
                "current_stock": stock.current_stock,
                "avg_monthly_consumption": monthly_consumption,
                "turnover_rate": turnover_rate,
                "suggested_reorder_point": int(monthly_consumption * 1.5),  # 1.5个月的库存
                "suggested_order_quantity": int(monthly_consumption * 2)  # 2个月的补货量
            })
    
    return analysis_results

def get_supplier_analysis(db: Session, days: int = 180):
    """获取供应商分析数据"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    suppliers = db.query(models.Supplier).all()
    analysis_results = []
    
    for supplier in suppliers:
        inbound_records = db.query(models.InboundRecord).filter(
            models.InboundRecord.supplier_id == supplier.id,
            models.InboundRecord.created_at.between(start_date, end_date)
        ).all()
        
        if inbound_records:
            total_deliveries = len(inbound_records)
            on_time_deliveries = sum(1 for r in inbound_records if True)  # 需要添加准时判断逻辑
            quality_issues = sum(1 for r in inbound_records if False)  # 需要添加质量问题判断逻辑
            
            analysis_results.append({
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "total_deliveries": total_deliveries,
                "on_time_rate": on_time_deliveries / total_deliveries if total_deliveries > 0 else 0,
                "quality_score": 1 - (quality_issues / total_deliveries if total_deliveries > 0 else 0),
                "avg_delivery_days": 3.5  # 需要添加实际送货时间计算
            })
    
    return analysis_results

def create_backup_record(db: Session, backup_type: str, operator_id: int):
    """创建备份记录"""
    backup_record = models.BackupRecord(
        backup_type=backup_type,
        operator_id=operator_id,
        status="pending"
    )
    db.add(backup_record)
    db.commit()
    db.refresh(backup_record)
    return backup_record

def perform_backup(db: Session, backup_id: int):
    """执行备份操作"""
    backup_record = db.query(models.BackupRecord).filter(
        models.BackupRecord.id == backup_id
    ).first()
    
    if not backup_record:
        return
    
    try:
        # 创建备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = BACKUP_DIR / f"backup_{backup_record.backup_type}_{timestamp}.sql"
        
        # 执行pg_dump
        subprocess.run([
            'pg_dump',
            '-h', 'localhost',
            '-U', 'user',
            '-d', 'warehouse_db',
            '-f', str(backup_file)
        ], check=True)
        
        backup_record.backup_path = str(backup_file)
        backup_record.status = "success"
        
    except Exception as e:
        backup_record.status = "failed"
        
    db.commit()

def restore_from_backup(db: Session, backup_id: int):
    """从备份恢复数据"""
    backup_record = db.query(models.BackupRecord).filter(
        models.BackupRecord.id == backup_id
    ).first()
    
    if not backup_record or backup_record.status != "success":
        raise HTTPException(status_code=400, detail="Invalid backup record")
    
    try:
        # 执行psql恢复
        subprocess.run([
            'psql',
            '-h', 'localhost',
            '-U', 'user',
            '-d', 'warehouse_db',
            '-f', backup_record.backup_path
        ], check=True)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Restore failed")

def get_backup_records(db: Session):
    """获取备份记录列表"""
    return db.query(models.BackupRecord).order_by(
        models.BackupRecord.created_at.desc()
    ).all() 