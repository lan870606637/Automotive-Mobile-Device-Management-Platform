# 设备管理系统 - 部署指南

## 一、快速启动（带端口号）

如果不需要隐藏端口号，直接运行：

```bash
python start_services.py
```

访问地址：
- 用户端：http://device.carbit.com.cn:5000
- 管理后台：http://admin.device.carbit.com.cn:5001

---

## 二、完整部署（不带端口号）

### 步骤1：下载Nginx

1. 访问 http://nginx.org/en/download.html
2. 下载 Windows 版本（如：nginx-1.24.0.zip）
3. 解压到项目目录，确保路径为：
   ```
   d:\Automotive-Mobile-Device-Management-Platform\nginx\
   ```

解压后的目录结构：
```
nginx/
├── conf/
├── contrib/
├── docs/
├── html/
├── logs/
├── temp/
├── nginx.exe          <-- 主程序
└── ...
```

### 步骤2：配置Nginx

我已经为你创建了Nginx配置文件 [nginx/nginx.conf](nginx/nginx.conf)。

将配置文件复制到Nginx目录：
```bash
copy nginx.conf nginx\conf\
```

### 步骤3：配置本地域名

**以管理员身份运行** `setup_domains.bat`：

1. 右键点击 `setup_domains.bat`
2. 选择"以管理员身份运行"
3. 脚本会自动配置hosts文件

或者手动编辑 `C:\Windows\System32\drivers\etc\hosts`，添加：
```
127.0.0.1       device.carbit.com.cn
127.0.0.1       admin.device.carbit.com.cn
```

### 步骤4：启动所有服务

**以管理员身份运行** `start_with_nginx.bat`：

1. 右键点击 `start_with_nginx.bat`
2. 选择"以管理员身份运行"

这个脚本会依次启动：
- 用户服务（端口5000）
- 管理服务（端口5001）
- Nginx反向代理（端口80）

### 步骤5：访问系统

现在可以通过以下地址访问（**无需端口号**）：

- **用户端**：http://device.carbit.com.cn
- **管理后台**：http://admin.device.carbit.com.cn

---

## 三、目录结构

```
d:\Automotive-Mobile-Device-Management-Platform\
├── user_service\              # 用户端服务
│   ├── app.py
│   └── templates\
├── admin_service\              # 管理后台服务
│   ├── app.py
│   └── templates\
├── nginx\                      # Nginx目录（需要下载）
│   ├── conf\
│   │   └── nginx.conf          # Nginx配置文件
│   └── nginx.exe
├── common\                     # 公共模块
│   └── config.py
├── nginx.conf                  # Nginx配置（备份）
├── start_services.py           # 基础启动脚本
├── start_with_nginx.bat        # 完整启动脚本（推荐）
├── setup_domains.bat           # 域名配置脚本
└── DEPLOY.md                   # 本文件
```

---

## 四、常见问题

### Q1: 80端口被占用

如果提示80端口被占用，可能是：
- IIS服务正在运行
- 其他Web服务器（如Apache、Tomcat）
- Skype等软件

**解决方法**：
1. 查找占用80端口的进程：
   ```cmd
   netstat -ano | findstr :80
   ```
2. 结束对应进程，或修改Nginx使用其他端口（如8080）

### Q2: 无法访问域名

1. 检查hosts文件是否正确配置
2. 刷新DNS缓存：
   ```cmd
   ipconfig /flushdns
   ```
3. 检查服务是否启动：
   ```cmd
   netstat -an | findstr :5000
   ```

### Q3: Nginx启动失败

1. 检查Nginx路径是否正确
2. 检查配置文件语法：
   ```cmd
   cd nginx
   nginx -t
   ```

---

## 五、停止服务

### 方法1：关闭启动窗口
直接关闭 `start_with_nginx.bat` 窗口即可。

### 方法2：手动停止
```cmd
taskkill /f /im nginx.exe
taskkill /f /im python.exe
```

---

## 六、技术说明

### 端口映射关系

| 服务 | 内部端口 | 外部访问 | 说明 |
|------|----------|----------|------|
| 用户端 | 5000 | 80 (Nginx转发) | Flask应用 |
| 管理后台 | 5001 | 80 (Nginx转发) | Flask应用 |
| Nginx | 80 | 80 | 反向代理 |

### Nginx工作原理

```
用户访问 http://device.carbit.com.cn
           ↓
      DNS解析到 127.0.0.1
           ↓
      Nginx (端口80)
           ↓
      根据server_name转发
           ↓
      Flask应用 (端口5000/5001)
```

---

## 七、测试账号

- 手机号：13800138001
- 密码：123456

---

## 八、技术支持

如有问题，请检查：
1. 所有服务是否已启动
2. hosts文件是否正确配置
3. Nginx配置是否正确
