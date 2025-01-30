from locust import HttpUser, task, between, events
from typing import Dict, Any
import json
import random
from datetime import datetime, timedelta

class WarehouseLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """用户登录"""
        response = self.client.post("/token", data={
            "username": "testuser",
            "password": "password123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def query_products(self):
        """查询商品列表"""
        self.client.get("/products/", headers=self.headers)
    
    @task(2)
    def check_stock(self):
        """查询库存"""
        product_id = random.randint(1, 100)
        self.client.get(f"/stock/{product_id}", headers=self.headers)
    
    @task(1)
    def create_inbound(self):
        """创建入库记录"""
        data = {
            "product_id": random.randint(1, 100),
            "warehouse_id": random.randint(1, 5),
            "supplier_id": random.randint(1, 10),
            "quantity": random.randint(10, 1000),
            "batch_number": f"BATCH-{random.randint(1000, 9999)}",
            "production_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "expiry_date": (datetime.now() + timedelta(days=365)).isoformat()
        }
        self.client.post("/inbound/", json=data, headers=self.headers)
    
    @task(1)
    def create_outbound(self):
        """创建出库记录"""
        data = {
            "product_id": random.randint(1, 100),
            "warehouse_id": random.randint(1, 5),
            "quantity": random.randint(1, 100),
            "reason": "Performance test"
        }
        self.client.post("/outbound/", json=data, headers=self.headers)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Starting performance test...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("Performance test completed") 