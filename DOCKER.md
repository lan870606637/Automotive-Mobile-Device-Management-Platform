# Docker 部署指南

## 文件说明

- **Dockerfile** - 应用容器镜像构建文件
- **docker-compose.yml** - 基础编排（MySQL + Redis + Web）
- **docker-compose.full.yml** - 完整编排（包含 Nginx 反向代理）
- **.env.docker** - Docker 环境变量配置
- **nginx.docker.conf** - Docker Nginx 配置文件

## 快速开始

### 1. 使用基础版本（推荐开发环境）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

访问地址：
- 用户端：http://localhost:5000
- 管理后台：http://localhost:5001
- 手机端：http://localhost:5002

### 2. 使用完整版本（推荐生产环境）

```bash
# 使用完整配置启动
docker-compose -f docker-compose.full.yml up -d

# 查看日志
docker-compose -f docker-compose.full.yml logs -f

# 停止服务
docker-compose -f docker-compose.full.yml down
```

访问地址：
- 用户端：http://localhost:80
- 管理后台：http://localhost:81
- 手机端：http://localhost:82

## 常用命令

```bash
# 构建镜像
docker-compose build

# 重新构建并启动
docker-compose up -d --build

# 查看运行状态
docker-compose ps

# 进入容器
docker-compose exec web bash
docker-compose exec mysql mysql -uroot -pcarbit2014

# 查看特定服务日志
docker-compose logs -f web
docker-compose logs -f mysql
docker-compose logs -f redis

# 重启服务
docker-compose restart web

# 停止并删除所有数据（慎用）
docker-compose down -v
```

## 数据持久化

数据通过 Docker volumes 持久化：
- `mysql-data` - MySQL 数据库数据
- `redis-data` - Redis 缓存数据
- `./logs` - 应用日志
- `./uploads` - 上传文件
- `./backups` - 数据库备份

## 环境变量

在 `.env.docker` 文件中配置：

```env
MYSQL_HOST=mysql          # MySQL 容器名
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=carbit2014
MYSQL_DATABASE=device_management

REDIS_HOST=redis          # Redis 容器名
REDIS_PORT=6379
```

## 数据库初始化

首次启动时，MySQL 会自动导入 `device_management_20260303_171833.sql` 文件。

如需重新初始化：
```bash
# 删除 MySQL 数据卷
docker-compose down -v

# 重新启动
docker-compose up -d
```

## 注意事项

1. **端口冲突**：确保本地 3306、6379、5000-5002、80-82 端口未被占用
2. **内存要求**：建议至少 2GB 可用内存
3. **防火墙**：确保 Docker 网络通信不被防火墙阻止

## 故障排查

### 服务无法启动
```bash
# 查看详细日志
docker-compose logs --tail=100

# 检查端口占用
netstat -ano | findstr :5000
```

### 数据库连接失败
```bash
# 检查 MySQL 健康状态
docker-compose ps

# 手动连接测试
docker-compose exec mysql mysql -uroot -pcarbit2014 -e "SHOW DATABASES;"
```

### 重新构建
```bash
# 清理并重建
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```
