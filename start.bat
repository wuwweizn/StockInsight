@echo off
chcp 65001 >nul
echo ========================================
echo   StockInsight - 股票洞察分析系统 v1.0.0
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo [信息] 检查Python环境...
python --version

REM 检查依赖是否安装
echo [信息] 检查依赖包...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [信息] 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖包安装失败
        pause
        exit /b 1
    )
)

echo [信息] 启动服务...
echo [信息] 服务地址: http://localhost:8588
echo [信息] 按 Ctrl+C 停止服务
echo.

python main.py

pause
