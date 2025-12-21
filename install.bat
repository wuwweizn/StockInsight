@echo off
chcp 65001 >nul
echo ========================================
echo   StockInsight - 股票洞察分析系统 v1.0.0 安装脚本
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

echo [信息] Python版本:
python --version

REM 检查pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到pip，请先安装pip
    pause
    exit /b 1
)

REM 升级pip
echo [信息] 升级pip...
python -m pip install --upgrade pip -q

REM 安装依赖
echo [信息] 安装依赖包...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [成功] 安装完成！
echo.
echo 启动方式：
echo   开发模式: python main.py
echo   生产模式: python start_prod.py
echo   或使用: start.bat
echo.
pause

