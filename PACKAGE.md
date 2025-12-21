# StockInsight - 股票洞察分析系统 v1.0.0 部署包说明

## 文件清单

### 核心文件（必需）
```
app/                    # 应用核心代码目录
├── __init__.py
├── api.py             # API路由
├── auth.py            # 认证授权
├── config.py          # 配置管理
├── database.py        # 数据库操作
├── data_fetcher.py    # 数据获取
├── data_updater.py    # 数据更新
├── permissions.py     # 权限定义
└── statistics.py      # 统计分析

static/                 # 静态文件目录
└── app.js            # 前端JavaScript

templates/              # HTML模板目录
└── index.html        # 主页面

main.py                # 开发模式启动入口
start_prod.py          # 生产环境启动脚本
requirements.txt       # Python依赖列表
```

### 部署文件
```
start.bat              # Windows启动脚本
start.sh               # Linux启动脚本
install.bat            # Windows安装脚本
install.sh             # Linux安装脚本
Dockerfile             # Docker镜像构建文件
docker-compose.yml     # Docker编排文件
.dockerignore          # Docker忽略文件
```

### 文档文件
```
README.md              # 项目说明
DEPLOYMENT.md          # 详细部署指南
PACKAGE.md             # 本文件
.gitignore             # Git忽略文件
```

## 部署方式选择

### 方式一：直接部署（推荐新手）
- **Windows**: 双击 `start.bat`
- **Linux**: 运行 `./start.sh`
- **优点**: 简单快速，适合本地开发和小规模使用
- **缺点**: 需要手动管理进程

### 方式二：VPS服务器部署（推荐生产环境）
- 使用 `systemd` 服务管理
- 可配置 Nginx 反向代理
- **优点**: 稳定可靠，易于管理
- **缺点**: 需要服务器管理经验

### 方式三：Docker部署（推荐容器化环境）
- 使用 `docker-compose up -d` 启动
- **优点**: 环境隔离，易于迁移和扩展
- **缺点**: 需要安装Docker

## 快速部署检查清单

### 直接部署
- [ ] Python 3.8+ 已安装
- [ ] 运行 `install.bat` (Windows) 或 `install.sh` (Linux)
- [ ] 运行 `start.bat` (Windows) 或 `./start.sh` (Linux)
- [ ] 访问 http://localhost:8588 测试

### VPS部署
- [ ] 上传所有文件到服务器
- [ ] 安装Python3和pip
- [ ] 运行 `./install.sh`
- [ ] 配置防火墙开放8588端口
- [ ] 配置systemd服务（可选）
- [ ] 配置Nginx反向代理（可选）

### Docker部署
- [ ] 安装Docker和Docker Compose
- [ ] 创建 `data` 目录用于数据持久化
- [ ] 运行 `docker-compose up -d`
- [ ] 检查日志：`docker-compose logs -f`

## 首次启动后

1. **登录系统**
   - 访问 http://localhost:8588
   - 使用默认账号：`admin` / `admin123`

2. **修改管理员密码**
   - 登录后立即修改密码
   - 路径：用户管理 → 编辑 → 修改密码

3. **配置数据源**
   - 进入"系统配置"
   - 配置Tushare Token或Finnhub API Key（如需要）

4. **更新数据**
   - 进入"数据管理"
   - 选择数据源
   - 执行"全量更新"或"增量更新"

## 数据备份

**重要**: 定期备份以下文件：
- `stock_data.db` - 数据库文件（最重要）
- `config.json` - 配置文件
- `update_progress.json` - 更新进度文件

## 升级说明

升级到新版本时：
1. 停止服务
2. 备份数据库和配置
3. 替换代码文件（保留数据库和配置）
4. 运行 `install.sh` 或 `install.bat` 更新依赖
5. 重启服务

## 技术支持

如有问题，请联系管理员微信：**yyongzf8**

