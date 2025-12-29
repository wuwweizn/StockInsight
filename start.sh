#!/bin/bash

echo "========================================"
echo "  StockInsight - 股票洞察分析系统 v1.0.0"
echo "========================================"
echo ""

BASE_DIR=$(cd "$(dirname "$0")" && pwd)
VENV_DIR="$BASE_DIR/env"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# 检查虚拟环境
if [ ! -f "$PYTHON" ]; then
    echo "[错误] 未找到虚拟环境，请先创建："
    echo "python3.11 -m venv env"
    exit 1
fi

echo "[信息] 使用 Python："
$PYTHON --version

# 检查 FastAPI 是否存在
echo "[信息] 检查依赖..."
$PYTHON - <<EOF
import fastapi
print("FastAPI OK")
EOF

if [ $? -ne 0 ]; then
    echo "[错误] 依赖未安装或 SSL 异常"
    echo "请先手动执行："
    echo "source env/bin/activate"
    echo "pip install -r requirements.txt"
    exit 1
fi

echo ""
echo "[信息] 启动 StockInsight 服务"
echo "[信息] 服务地址: http://0.0.0.0:8588"
echo "[信息] 按 Ctrl+C 停止"
echo ""

exec $PYTHON main.py
