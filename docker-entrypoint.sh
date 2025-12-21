#!/bin/bash
set -e

# 设置数据目录（可通过环境变量覆盖）
DATA_DIR=${DATA_DIR:-/app/data}
mkdir -p "$DATA_DIR"

# 设置数据库和配置文件路径
DB_PATH="$DATA_DIR/stock_data.db"
CONFIG_PATH="$DATA_DIR/config.json"

# 如果数据库文件不存在，初始化数据库
if [ ! -f "$DB_PATH" ]; then
    echo "初始化数据库: $DB_PATH"
    python -c "from app.database import Database; Database(db_path='$DB_PATH')"
fi

# 如果配置文件不存在，创建默认配置
if [ ! -f "$CONFIG_PATH" ]; then
    echo "创建默认配置文件: $CONFIG_PATH"
    python -c "from app.config import Config; Config(config_file='$CONFIG_PATH')"
fi

# 设置环境变量，让应用使用挂载的数据目录
export DB_PATH="$DB_PATH"
export CONFIG_PATH="$CONFIG_PATH"

# 启动应用
exec python start_prod.py

