from fastapi import FastAPI, Depends, HTTPException, Security, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
import csv
import os
from datetime import datetime, timedelta
from . import crud, models, schemas, security
from .database import SessionLocal, engine
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from .middleware import performance_middleware
from .middleware.security import security_middleware
from .security_config import security_settings
from .security.middleware import security_middleware
from .security.config import security_config

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Warehouse Management System",
    description="""
    仓库管理系统API文档
    
    功能包括：
    * 用户认证和权限管理
    * 商品和库存管理
    * 入库和出库操作
    * 库存预警
    * 数据统计和分析
    * 数据导出
    * 离线同步
    * 数据备份
    """,
    version="1.0.0"
)

# 创建Prometheus metrics endpoint
metrics_app = make_asgi_app()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=security_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=security_config.CORS_METHODS,
    allow_headers=security_config.CORS_HEADERS,
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/products/", response_model=List[schemas.Product])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = crud.get_products(db, skip=skip, limit=limit)
    return products

@app.post("/products/", response_model=schemas.Product)
def create_product(
    product: schemas.ProductCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    return crud.create_product(db=db, product=product)

@app.post("/inbound/", response_model=schemas.InboundRecord)
def create_inbound_record(
    inbound: schemas.InboundRecordCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("warehouse"))
):
    return crud.create_inbound_record(db=db, inbound=inbound, operator_id=current_user.id)

@app.post("/outbound/", response_model=schemas.OutboundRecord)
def create_outbound_record(
    outbound: schemas.OutboundRecordCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("warehouse"))
):
    return crud.create_outbound_record(db=db, outbound=outbound, operator_id=current_user.id)

@app.get("/stock/{product_id}", response_model=List[schemas.Stock])
def read_product_stock(product_id: int, db: Session = Depends(get_db)):
    stocks = crud.get_product_stock(db, product_id=product_id)
    return stocks

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = crud.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(
        data={"sub": user.username}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/stock/warnings", response_model=List[schemas.StockWarning])
def get_stock_warnings(db: Session = Depends(get_db)):
    return crud.get_stock_warnings(db)

@app.get("/stock/expiry-warnings", response_model=List[schemas.ExpiryWarning])
def get_expiry_warnings(db: Session = Depends(get_db)):
    return crud.get_expiry_warnings(db)

@app.post("/stock/transfer", response_model=schemas.StockTransfer)
def transfer_stock(
    transfer: schemas.StockTransferCreate,
    db: Session = Depends(get_db)
):
    return crud.create_stock_transfer(db, transfer)

@app.get("/statistics/stock")
def get_stock_statistics(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db)
):
    return crud.get_stock_statistics(db, start_date, end_date)

@app.get("/statistics/supplier")
def get_supplier_statistics(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db)
):
    return crud.get_supplier_statistics(db, start_date, end_date)

@app.get("/logs/operations", response_model=List[schemas.OperationLog])
def get_operation_logs(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    operation_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    return crud.get_operation_logs(
        db, 
        start_date=start_date, 
        end_date=end_date, 
        operation_type=operation_type
    )

# 条码扫描
@app.post("/barcode/scan", response_model=schemas.BarcodeResponse)
def scan_barcode(
    barcode_info: schemas.BarcodeInfo,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("warehouse"))
):
    return crud.process_barcode(db, barcode_info)

# 数据导出
@app.get("/export/stock")
def export_stock_data(
    warehouse_id: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    file_path = crud.export_stock_data(db, warehouse_id, category)
    return FileResponse(
        file_path,
        filename=f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

@app.get("/export/transactions")
def export_transactions(
    start_date: datetime,
    end_date: datetime,
    transaction_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    file_path = crud.export_transactions(db, start_date, end_date, transaction_type)
    return FileResponse(
        file_path,
        filename=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

# 离线同步
@app.post("/sync/queue", response_model=schemas.SyncQueue)
def add_to_sync_queue(
    operation_type: str,
    data: dict,
    db: Session = Depends(get_db)
):
    return crud.queue_offline_operation(db, operation_type, data)

@app.post("/sync/process")
def process_sync_queue(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    crud.process_sync_queue(db)
    return {"message": "Sync queue processed"}

# 高级分析
@app.get("/analysis/inventory", response_model=List[schemas.InventoryAnalysis])
def get_inventory_analysis(
    days: int = 90,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    return crud.get_inventory_analysis(db, days)

@app.get("/analysis/supplier", response_model=List[schemas.SupplierAnalysis])
def get_supplier_analysis(
    days: int = 180,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    return crud.get_supplier_analysis(db, days)

# 数据备份
@app.post("/backup/create", response_model=schemas.BackupRecord)
def create_backup(
    backup_type: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    """
    创建数据备份
    
    - **backup_type**: 备份类型 (full/incremental)
    """
    backup_record = crud.create_backup_record(db, backup_type, current_user.id)
    background_tasks.add_task(crud.perform_backup, db, backup_record.id)
    return backup_record

@app.post("/backup/restore/{backup_id}")
def restore_backup(
    backup_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    """
    从备份恢复数据
    
    - **backup_id**: 备份记录ID
    """
    background_tasks.add_task(crud.restore_from_backup, db, backup_id)
    return {"message": "Restore process started"}

@app.get("/backup/list", response_model=List[schemas.BackupRecord])
def list_backups(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    """获取备份记录列表"""
    return crud.get_backup_records(db)

# 自定义OpenAPI文档
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="仓库管理系统API",
        version="1.0.0",
        description="仓库管理系统API文档",
        routes=app.routes,
    )
    
    # 添加安全配置
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi 

@app.middleware("http")
async def add_performance_middleware(request: Request, call_next):
    return await performance_middleware(request, call_next)

# 添加Prometheus metrics endpoint
app.mount("/metrics", metrics_app)

# 添加健康检查endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# 添加系统状态检查
@app.get("/status")
async def system_status(
    current_user: models.User = Depends(security.check_permissions("admin"))
):
    return {
        "database": check_database_connection(),
        "redis": check_redis_connection(),
        "disk_usage": get_disk_usage(),
        "memory_usage": get_memory_usage(),
        "backup_status": get_last_backup_status()
    }

# 添加安全中间件
app.middleware("http")(security_middleware) 