FROM python:3.9

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY ./app ./app
COPY ./alembic.ini .
COPY ./migrations ./migrations

# 创建必要的目录
RUN mkdir -p /app/temp /app/backups

# 设置环境变量
ENV PYTHONPATH=/app
ENV DATABASE_URL=postgresql://user:password@db/warehouse_db
ENV REDIS_URL=redis://redis:6379/0

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 