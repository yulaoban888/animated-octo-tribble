import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from app import crud, models, schemas
from app.database import Base

# 测试数据库配置
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/test_warehouse_db"

@pytest.fixture
def db_session():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_create_user(db_session):
    user = schemas.UserCreate(
        username="testuser",
        email="test@example.com",
        password="password123",
        role="admin"
    )
    db_user = crud.create_user(db_session, user)
    assert db_user.username == "testuser"
    assert db_user.email == "test@example.com"
    assert db_user.role == "admin"

def test_create_product(db_session):
    product = schemas.ProductCreate(
        name="Test Product",
        barcode="123456789",
        category="Test Category",
        unit="piece",
        price=10.0,
        min_stock=5
    )
    db_product = crud.create_product(db_session, product)
    assert db_product.name == "Test Product"
    assert db_product.barcode == "123456789"

def test_inbound_record(db_session):
    # 创建测试数据
    product = crud.create_product(db_session, schemas.ProductCreate(
        name="Test Product",
        barcode="123456789",
        category="Test",
        unit="piece",
        price=10.0
    ))
    
    inbound = schemas.InboundRecordCreate(
        product_id=product.id,
        warehouse_id=1,
        supplier_id=1,
        quantity=100,
        batch_number="TEST001",
        production_date=datetime.now(),
        expiry_date=datetime.now() + timedelta(days=90)
    )
    
    db_inbound = crud.create_inbound_record(db_session, inbound, operator_id=1)
    assert db_inbound.quantity == 100
    
    # 验证库存更新
    stock = crud.get_product_stock(db_session, product.id)[0]
    assert stock.quantity == 100

def test_outbound_record(db_session):
    # 先创建入库记录
    product = crud.create_product(db_session, schemas.ProductCreate(
        name="Test Product",
        barcode="123456789",
        category="Test",
        unit="piece",
        price=10.0
    ))
    
    inbound = schemas.InboundRecordCreate(
        product_id=product.id,
        warehouse_id=1,
        supplier_id=1,
        quantity=100,
        batch_number="TEST001",
        production_date=datetime.now(),
        expiry_date=datetime.now() + timedelta(days=90)
    )
    crud.create_inbound_record(db_session, inbound, operator_id=1)
    
    # 测试出库
    outbound = schemas.OutboundRecordCreate(
        product_id=product.id,
        warehouse_id=1,
        quantity=50,
        reason="Test outbound"
    )
    
    db_outbound = crud.create_outbound_record(db_session, outbound)
    assert db_outbound.quantity == 50
    
    # 验证库存更新
    stock = crud.get_product_stock(db_session, product.id)[0]
    assert stock.quantity == 50

def test_insufficient_stock(db_session):
    product = crud.create_product(db_session, schemas.ProductCreate(
        name="Test Product",
        barcode="123456789",
        category="Test",
        unit="piece",
        price=10.0
    ))
    
    outbound = schemas.OutboundRecordCreate(
        product_id=product.id,
        warehouse_id=1,
        quantity=50,
        reason="Test outbound"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        crud.create_outbound_record(db_session, outbound)
    assert exc_info.value.status_code == 400 