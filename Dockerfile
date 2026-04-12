# Dockerfile - 稳定版
FROM python:3.9-slim-bookworm

# 设置工作目录
WORKDIR /app

# 彻底清理并配置阿里云源
RUN rm -rf /etc/apt/sources.list.d/* && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main contrib non-free" >> /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libmariadb-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（利用缓存）
COPY requirements.txt .

# 使用国内 pip 源安装依赖
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制整个项目
COPY . .

# 使用 Docker 环境配置
RUN cp .env.docker .env

# 创建必要的目录
RUN mkdir -p logs backups uploads data

# 暴露端口
EXPOSE 5000 5001 5002

# 启动命令
CMD ["python", "start.py"]
