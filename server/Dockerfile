FROM python:3.13-slim

WORKDIR /app

# M2-07: 移除 build-essential / libpcap-dev 减小镜像 / 加速 build
# (绝大多数 Python 依赖有 wheel,本项目运行时不需要本地编译)
# tcpdump / net-tools 保留以便 debug 时使用
RUN apt-get update && apt-get install -y --no-install-recommends \
    tcpdump net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# M2-07: backend / migrate 都依赖 alembic 配置和 migrations 目录
# (migrations/env.py: sys.path 注入 + Base.metadata 加载 + DATABASE_URL 解析)
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/

COPY server/ ./server/

RUN mkdir -p /app/data && adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app

ENV BIND_HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

USER appuser

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
