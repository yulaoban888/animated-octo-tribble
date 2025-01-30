from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    WAREHOUSE = "warehouse"
    FINANCE = "finance"

class UserBase(BaseModel):
    username: str
    email: str
    role: UserRole

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class ProductBase(BaseModel):
    name: str
    barcode: str
    category: str
    unit: str
    price: float
    min_stock: int = 0

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class StockBase(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int
    shelf_number: str
    expiry_date: datetime

class StockCreate(StockBase):
    pass

class Stock(StockBase):
    id: int
    
    class Config:
        orm_mode = True

class InboundRecordBase(BaseModel):
    product_id: int
    warehouse_id: int
    supplier_id: int
    quantity: int
    batch_number: str
    production_date: datetime
    expiry_date: datetime

class InboundRecordCreate(InboundRecordBase):
    pass

class InboundRecord(InboundRecordBase):
    id: int
    operator_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class OutboundRecordBase(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int
    order_id: Optional[str]
    reason: str

class OutboundRecordCreate(OutboundRecordBase):
    pass

class OutboundRecord(OutboundRecordBase):
    id: int
    operator_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class StockWarning(BaseModel):
    product: Product
    current_quantity: int
    min_stock: int
    warehouse: str

class ExpiryWarning(BaseModel):
    product: Product
    quantity: int
    expiry_date: datetime
    days_until_expiry: int
    warehouse: str

class StockTransferCreate(BaseModel):
    product_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: int
    reason: str

class StockTransfer(StockTransferCreate):
    id: int
    created_at: datetime
    operator_id: int

    class Config:
        orm_mode = True

class OperationLog(BaseModel):
    id: int
    operation_type: str
    operation_detail: str
    operator_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class BarcodeInfo(BaseModel):
    barcode: str
    product_id: Optional[int]
    name: Optional[str]
    category: Optional[str]
    unit: Optional[str]
    price: Optional[float]

class BarcodeResponse(BaseModel):
    exists: bool
    product: Optional[Product]

class SyncQueueBase(BaseModel):
    operation_type: str
    data: str
    status: str = "pending"

class SyncQueue(SyncQueueBase):
    id: int
    retry_count: int
    created_at: datetime
    last_attempt: Optional[datetime]

    class Config:
        orm_mode = True

class InventoryAnalysis(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    avg_monthly_consumption: float
    turnover_rate: float
    suggested_reorder_point: int
    suggested_order_quantity: int

class SupplierAnalysis(BaseModel):
    supplier_id: int
    supplier_name: str
    total_deliveries: int
    on_time_rate: float
    quality_score: float
    avg_delivery_days: float

class BackupRecordBase(BaseModel):
    backup_type: str
    status: str = "pending"

class BackupRecord(BackupRecordBase):
    id: int
    backup_path: str
    operator_id: int
    created_at: datetime

    class Config:
        orm_mode = True 