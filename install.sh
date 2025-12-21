#!/bin/bash

echo "========================================"
echo "  StockInsight - 股票洞察分析系统 v1.0.0 安装脚本"
echo "========================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python3，请先安装Python 3.11+"
    exit 1
fi

echo "[信息] Python版本: $(python3 --version)"

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo "[错误] 未检测到pip3，请先安装pip"
    exit 1
fi

# 升级pip
echo "[信息] 升级pip..."
pip3 install --upgrade pip -q

# 安装依赖
echo "[信息] 安装依赖包..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "[成功] 安装完成！"
    echo ""
    echo "启动方式："
    echo "  开发模式: python3 main.py"
    echo "  生产模式: python3 start_prod.py"
    echo "  或使用: ./start.sh"
    echo ""
else
    echo "[错误] 依赖安装失败"
    exit 1
fi

