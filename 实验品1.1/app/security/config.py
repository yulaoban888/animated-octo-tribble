from pydantic import BaseSettings
from typing import List, Optional
import re

class SecurityConfig(BaseSettings):
    # JWT设置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 密码策略
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    
    # 请求限制
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 100
    
    # IP白名单/黑名单
    IP_WHITELIST: List[str] = []
    IP_BLACKLIST: List[str] = []
    
    # 会话安全
    SESSION_TIMEOUT_MINUTES: int = 60
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 30
    
    # CORS设置
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # 安全头部
    SECURITY_HEADERS: dict = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'"
    }
    
    class Config:
        env_file = ".env"

    def validate_password(self, password: str) -> bool:
        """验证密码强度"""
        if len(password) < self.PASSWORD_MIN_LENGTH:
            return False
        
        if self.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            return False
            
        if self.PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            return False
            
        if self.PASSWORD_REQUIRE_NUMBERS and not re.search(r"\d", password):
            return False
            
        if self.PASSWORD_REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False
            
        return True

security_config = SecurityConfig() 