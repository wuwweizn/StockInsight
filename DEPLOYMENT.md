# StockInsight - 股票洞察分析系统 v1.0.0 部署指南

## 系统要求

- Python 3.8 或更高版本
- 至少 2GB 可用内存
- 至少 1GB 可用磁盘空间（用于数据库存储）

## 方式一：直接部署（Windows/Linux）

### Windows 部署

1. **安装Python**
   - 下载并安装 Python 3.8+：https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"

2. **部署系统**
   ```cmd
   # 解压或克隆项目到目标目录
   cd C:\GPFX2
   
   # 运行启动脚本（会自动安装依赖）
   start.bat
   ```

3. **访问系统**
   - 打开浏览器访问：http://localhost:8588
   - 默认管理员账号：`admin` / `admin123`

### Linux 部署

1. **安装Python3**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3 python3-pip -y
   
   # CentOS/RHEL
   sudo yum install python3 python3-pip -y
   ```

2. **部署系统**
   ```bash
   # 解压或克隆项目到目标目录
   cd /opt/gpfx2
   
   # 添加执行权限
   chmod +x start.sh
   
   # 运行启动脚本（会自动安装依赖）
   ./start.sh
   ```

3. **访问系统**
   - 打开浏览器访问：http://服务器IP:8588
   - 默认管理员账号：`admin` / `admin123`

### 后台运行（Linux）

使用 `nohup` 或 `systemd` 服务：

**方式1：使用 nohup**
```bash
nohup python3 start_prod.py > app.log 2>&1 &
```

**方式2：使用 systemd（推荐）**

创建服务文件 `/etc/systemd/system/stock-analysis.service`：
```ini
[Unit]
Description=Stock Analysis System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/gpfx2
ExecStart=/usr/bin/python3 /opt/gpfx2/start_prod.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-analysis
sudo systemctl start stock-analysis
sudo systemctl status stock-analysis
```

## 方式二：VPS服务器部署

### 1. 上传文件到服务器

使用 `scp` 或 `FTP` 工具上传项目文件到服务器：
```bash
scp -r C:\GPFX2 user@your-server-ip:/opt/gpfx2
```

### 2. 安装依赖

```bash
cd /opt/gpfx2
pip3 install -r requirements.txt
```

### 3. 配置防火墙

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 8588/tcp
sudo ufw reload

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8588/tcp
sudo firewall-cmd --reload
```

### 4. 启动服务

```bash
# 使用 systemd（推荐）
sudo systemctl start stock-analysis

# 或使用 nohup
nohup python3 start_prod.py > app.log 2>&1 &
```

### 5. 配置Nginx反向代理（可选）

创建 `/etc/nginx/sites-available/stock-analysis`：
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8588;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/stock-analysis /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 方式三：Docker部署

### 1. 安装Docker和Docker Compose

**Windows/Mac:**
- 下载并安装 Docker Desktop：https://www.docker.com/products/docker-desktop

**Linux:**
```bash
# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 准备部署目录

```bash
# 创建部署目录
mkdir -p /opt/gpfx2
cd /opt/gpfx2

# 复制项目文件（不包括数据库和测试文件）
# 确保包含以下文件：
# - app/
# - static/
# - templates/
# - main.py
# - start_prod.py
# - requirements.txt
# - Dockerfile
# - docker-compose.yml
# - config.json（可选，可通过环境变量配置）
```

### 3. 配置数据持久化

```bash
# 创建数据目录
mkdir -p ./data

# 如果需要，复制现有数据库
# cp stock_data.db ./data/
```

### 4. 启动Docker容器

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps
```

### 5. 停止和重启

```bash
# 停止
docker-compose down

# 重启
docker-compose restart

# 更新代码后重新构建
docker-compose up -d --build
```

### 6. 数据备份

```bash
# 备份数据库
docker cp stock-analysis-v1:/app/data/stock_data.db ./backup/

# 或直接备份数据目录
tar -czf backup-$(date +%Y%m%d).tar.gz ./data
```

## 配置说明

### 环境变量（可选）

可以通过环境变量覆盖配置：
- `DATA_SOURCE`: 默认数据源（akshare/tushare/baostock/finnhub）
- `TUSHARE_TOKEN`: Tushare API Token
- `FINNHUB_API_KEY`: Finnhub API Key

### 配置文件

编辑 `config.json` 修改配置：
```json
{
    "data_source": "akshare",
    "tushare": {
        "token": "your_token"
    },
    "finnhub": {
        "api_key": "your_api_key"
    }
}
```

## 默认账号

- **管理员账号**: `admin`
- **默认密码**: `admin123`

**首次登录后请立即修改密码！**

## 端口配置

默认端口：`8588`

如需修改端口：
- **直接部署**: 修改 `main.py` 或 `start_prod.py` 中的 `port=8588`
- **Docker部署**: 修改 `docker-compose.yml` 中的端口映射

## 数据存储

- **数据库文件**: `stock_data.db`（SQLite）
- **配置文件**: `config.json`
- **进度文件**: `update_progress.json`

**重要**: 定期备份 `stock_data.db` 文件！

## 常见问题

### 1. 端口被占用

```bash
# Linux/Mac 查看端口占用
lsof -i :8588

# Windows 查看端口占用
netstat -ano | findstr :8588
```

### 2. 依赖安装失败

```bash
# 升级pip
pip install --upgrade pip

# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 数据库权限问题（Linux）

```bash
# 确保数据库文件有写权限
chmod 666 stock_data.db
chown www-data:www-data stock_data.db
```

### 4. Docker容器无法访问

- 检查防火墙设置
- 检查端口映射是否正确
- 查看容器日志：`docker-compose logs`

## 更新系统

1. 停止服务
2. 备份数据库和配置
3. 更新代码文件
4. 重启服务

## 技术支持

如有问题，请联系管理员微信：**yyongzf8**

