from fastapi.testclient import TestClient
from app.main import app
import pytest
from datetime import datetime, timedelta

def test_create_user(client):
    response = client.post(
        "/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "role": "admin"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "password" not in data

def test_login(client):
    # 先创建用户
    client.post(
        "/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "role": "admin"
        }
    )
    
    # 测试登录
    response = client.post(
        "/token",
        data={
            "username": "testuser",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_create_product_unauthorized(client):
    response = client.post(
        "/products/",
        json={
            "name": "Test Product",
            "barcode": "123456789",
            "category": "Test",
            "unit": "piece",
            "price": 10.0
        }
    )
    assert response.status_code == 401

def test_create_product_authorized(client, admin_token):
    response = client.post(
        "/products/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Test Product",
            "barcode": "123456789",
            "category": "Test",
            "unit": "piece",
            "price": 10.0
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Product" 