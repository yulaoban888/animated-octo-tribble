from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.sql import Select
from typing import Optional
import random

class DBRouter:
    def __init__(self):
        self.master_engine: Optional[Engine] = None
        self.slave_engines: list[Engine] = []
    
    def add_master(self, engine: Engine):
        """添加主数据库"""
        self.master_engine = engine
    
    def add_slave(self, engine: Engine):
        """添加从数据库"""
        self.slave_engines.append(engine)
    
    def get_engine(self, operation: str = "read") -> Engine:
        """获取数据库连接"""
        if operation == "write" or not self.slave_engines:
            return self.master_engine
        return random.choice(self.slave_engines)

# 创建路由实例
db_router = DBRouter()

@event.listens_for(Select, "before_compile")
def route_to_slave(query):
    """将查询路由到从库"""
    if not query.is_update and not query.is_delete:
        query._execution_options = {"use_slave": True} 